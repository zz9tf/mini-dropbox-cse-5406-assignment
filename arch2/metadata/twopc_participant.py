"""
2PC Participant for Metadata Node
Vote phase: prepare metadata (but don't update)
Decision phase: commit (update FILES) or abort (discard)
"""

import grpc
import logging
import os
import json
from concurrent import futures

try:
    from protos import twopc_pb2
    from protos import twopc_pb2_grpc
except ImportError:
    import twopc_pb2
    import twopc_pb2_grpc

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

NODE_ID = os.environ.get('NODE_ID', 'metadata')

# Shared pending transactions and metadata store reference
pending_transactions = {}
metadata_store = None  # Will be set by serve() function


class MetadataVotePhaseService(twopc_pb2_grpc.VotePhaseServiceServicer):
    """Vote phase service - prepare metadata but don't commit"""
    
    def Vote(self, request, context):
        """Handle vote request from coordinator - prepare metadata"""
        logger.info(f"Phase vote of Node {NODE_ID} runs RPC VoteRequest called by Phase coordinator of Node {request.node_id}")
        
        transaction_id = request.transaction_id
        operation = request.operation
        
        try:
            if operation == "upload":
                # Parse metadata
                metadata_json = request.metadata_json
                metadata = json.loads(metadata_json)
                
                # Store transaction data for decision phase (prepare but don't commit)
                pending_transactions[transaction_id] = {
                    'operation': operation,
                    'metadata': metadata
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


class MetadataDecisionPhaseService(twopc_pb2_grpc.DecisionPhaseServiceServicer):
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
                # Commit: actually update metadata (execute original HTTP API operation)
                if transaction['operation'] == "upload":
                    if metadata_store is not None:
                        metadata = transaction['metadata']
                        filename = metadata.get('filename')
                        if filename:
                            metadata_store[filename] = metadata
                            logger.info(f"Phase decision of Node {NODE_ID} committed transaction {transaction_id} - metadata updated for {filename} (store id: {id(metadata_store)})")
                    else:
                        logger.error(f"Phase decision of Node {NODE_ID}: metadata_store is None! Cannot update metadata for transaction {transaction_id}")
                
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


def serve(metadata_store_ref=None):
    """Start the metadata participant gRPC server"""
    global metadata_store
    metadata_store = metadata_store_ref  # Set reference to FILES dict from app.py
    logger.info(f"Metadata store reference set: {metadata_store is not None}, id: {id(metadata_store) if metadata_store is not None else None}, type: {type(metadata_store)}")
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    
    vote_service = MetadataVotePhaseService()
    decision_service = MetadataDecisionPhaseService()
    
    twopc_pb2_grpc.add_VotePhaseServiceServicer_to_server(vote_service, server)
    twopc_pb2_grpc.add_DecisionPhaseServiceServicer_to_server(decision_service, server)
    
    port = os.environ.get('PARTICIPANT_PORT', '6002')
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    logger.info(f"Metadata participant server started on port {port}")
    
    return server  # Return server so it can be managed by caller
