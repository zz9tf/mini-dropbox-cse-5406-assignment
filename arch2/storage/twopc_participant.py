"""
2PC Participant for Storage Node
Vote phase: prepare file data (but don't save)
Decision phase: commit (save file) or abort (discard)
"""

import grpc
import logging
import os
import base64
from concurrent import futures

try:
    from protos import twopc_pb2
    from protos import twopc_pb2_grpc
except ImportError:
    import twopc_pb2
    import twopc_pb2_grpc

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

NODE_ID = os.environ.get('NODE_ID', 'storage')
STORAGE_PATH = os.environ.get('STORAGE_PATH', '/storage')
os.makedirs(STORAGE_PATH, exist_ok=True)

# Shared pending transactions between vote and decision phases
pending_transactions = {}


class StorageVotePhaseService(twopc_pb2_grpc.VotePhaseServiceServicer):
    """Vote phase service - prepare file data but don't commit"""
    
    def Vote(self, request, context):
        """Handle vote request from coordinator - prepare file data"""
        logger.info(f"Phase vote of Node {NODE_ID} runs RPC VoteRequest called by Phase coordinator of Node {request.node_id}")
        
        transaction_id = request.transaction_id
        operation = request.operation
        
        try:
            if operation == "upload":
                # Prepare to save file (but don't commit yet)
                filename = request.filename
                file_data_b64 = request.file_data
                file_data = base64.b64decode(file_data_b64)
                
                # Check if we can save the file
                save_path = os.path.join(STORAGE_PATH, filename)
                
                # Store transaction data for decision phase (prepare but don't commit)
                pending_transactions[transaction_id] = {
                    'operation': operation,
                    'filename': filename,
                    'file_data': file_data,
                    'save_path': save_path
                }
                
                logger.info(f"Phase vote of Node {NODE_ID} prepared transaction {transaction_id}")
                return twopc_pb2.VoteResponse(
                    vote_commit=True,
                    message="Ready to commit",
                    node_id=NODE_ID
                )
            else:
                return twopc_pb2.VoteResponse(
                    vote_commit=False,
                    message=f"Unknown operation: {operation}",
                    node_id=NODE_ID
                )
        except Exception as e:
            logger.error(f"Error in vote phase: {e}")
            return twopc_pb2.VoteResponse(
                vote_commit=False,
                message=f"Error: {str(e)}",
                node_id=NODE_ID
            )


class StorageDecisionPhaseService(twopc_pb2_grpc.DecisionPhaseServiceServicer):
    """Decision phase service - commit or abort based on coordinator decision"""
    
    def Decision(self, request, context):
        """Handle decision request from coordinator - execute or abort"""
        decision_type = "global-commit" if request.global_commit else "global-abort"
        logger.info(f"Phase decision of Node {NODE_ID} runs RPC DecisionRequest called by Phase decision of Node {request.node_id}")
        
        transaction_id = request.transaction_id
        
        try:
            if transaction_id not in pending_transactions:
                return twopc_pb2.DecisionResponse(
                    success=False,
                    message="Transaction not found",
                    node_id=NODE_ID
                )
            
            transaction = pending_transactions[transaction_id]
            
            if request.global_commit:
                # Commit: actually save the file (execute original HTTP API operation)
                if transaction['operation'] == "upload":
                    with open(transaction['save_path'], 'wb') as f:
                        f.write(transaction['file_data'])
                    logger.info(f"Phase decision of Node {NODE_ID} committed transaction {transaction_id} - file saved to {transaction['save_path']}")
                
                # Remove from pending
                del pending_transactions[transaction_id]
                
                return twopc_pb2.DecisionResponse(
                    success=True,
                    message="Transaction committed",
                    node_id=NODE_ID
                )
            else:
                # Abort: discard the prepared transaction
                logger.info(f"Phase decision of Node {NODE_ID} aborted transaction {transaction_id}")
                del pending_transactions[transaction_id]
                
                return twopc_pb2.DecisionResponse(
                    success=True,
                    message="Transaction aborted",
                    node_id=NODE_ID
                )
        except Exception as e:
            logger.error(f"Error in decision phase: {e}")
            return twopc_pb2.DecisionResponse(
                success=False,
                message=f"Error: {str(e)}",
                node_id=NODE_ID
            )


def serve():
    """Start the storage participant gRPC server"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    
    vote_service = StorageVotePhaseService()
    decision_service = StorageDecisionPhaseService()
    
    twopc_pb2_grpc.add_VotePhaseServiceServicer_to_server(vote_service, server)
    twopc_pb2_grpc.add_DecisionPhaseServiceServicer_to_server(decision_service, server)
    
    port = os.environ.get('PARTICIPANT_PORT', '6001')
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    logger.info(f"Storage participant server started on port {port}")
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down storage participant server")
        server.stop(0)


if __name__ == '__main__':
    serve()
