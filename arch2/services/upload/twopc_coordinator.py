"""
2PC Coordinator - Integrated into Upload Service
Vote phase: verify all nodes are alive and prepare operations
Decision phase: send decision to participants, they execute operations directly in their decision phase
"""

import grpc
import logging
import os
import json
import base64
import uuid
from typing import List, Optional

try:
    from protos import twopc_pb2
    from protos import twopc_pb2_grpc
except ImportError:
    import twopc_pb2
    import twopc_pb2_grpc

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

NODE_ID = os.environ.get('NODE_ID', 'coordinator')
STORAGE_NODES = os.environ.get('STORAGE_NODES', 'storage:6001').split(',')
METADATA_NODES = os.environ.get('METADATA_NODES', 'metadata:6002').split(',')


class TwoPhaseCommitCoordinator:
    """Simple 2PC Coordinator: verify all nodes are alive, then execute operation"""
    
    def __init__(self):
        logger.info(f"Phase coordinator of Node {NODE_ID} initialized")
    
    def _create_channel(self, endpoint: str) -> Optional[grpc.Channel]:
        """Create gRPC channel to a participant node"""
        try:
            channel = grpc.insecure_channel(endpoint)
            return channel
        except Exception as e:
            logger.error(f"Failed to create channel to {endpoint}: {e}")
            return None
    
    def _send_vote_request(self, stub: twopc_pb2_grpc.VotePhaseServiceStub,
                          request: twopc_pb2.VoteRequest, node_id: str) -> Optional[twopc_pb2.VoteResponse]:
        """Send vote request to a participant"""
        try:
            logger.info(f"Phase coordinator of Node {NODE_ID} sends RPC VoteRequest to Phase vote of Node {node_id}")
            response = stub.Vote(request, timeout=5)
            logger.info(f"Phase vote of Node {node_id} sends RPC VoteResponse to Phase coordinator of Node {NODE_ID}: {response.message} (Vote: {response.vote_commit})")
            return response
        except grpc.RpcError as e:
            logger.error(f"RPC error from {node_id}: {e.code()} - {e.details()}")
            return None
    
    def _send_decision(self, stub: twopc_pb2_grpc.DecisionPhaseServiceStub,
                      request: twopc_pb2.DecisionRequest, node_id: str) -> Optional[twopc_pb2.DecisionResponse]:
        """Send decision to a participant"""
        try:
            decision_type = "global-commit" if request.global_commit else "global-abort"
            logger.info(f"Phase decision of Node {NODE_ID} sends RPC DecisionRequest to Phase decision of Node {node_id}")
            response = stub.Decision(request, timeout=5)
            logger.info(f"Phase decision of Node {node_id} sends RPC DecisionResponse to Phase decision of Node {NODE_ID}: {response.message} (Success: {response.success})")
            return response
        except grpc.RpcError as e:
            logger.error(f"RPC error from {node_id}: {e.code()} - {e.details()}")
            return None
    
    def execute_2pc_upload(self, filename: str, file_data: bytes, metadata: dict) -> dict:
        """
        Execute 2PC protocol for file upload
        Phase 1: Vote - verify all nodes are alive and prepare operations
        Phase 2: Decision - send decision to all participants, they execute operations directly
        """
        transaction_id = str(uuid.uuid4())
        logger.info(f"Phase coordinator of Node {NODE_ID} starting 2PC transaction {transaction_id}")
        
        # Encode file data to base64
        file_data_b64 = base64.b64encode(file_data).decode('utf-8')
        metadata_json = json.dumps(metadata)
        
        # Prepare vote request
        vote_request = twopc_pb2.VoteRequest(
            transaction_id=transaction_id,
            operation="upload",
            filename=filename,
            file_data=file_data_b64,
            metadata_json=metadata_json,
            node_id=NODE_ID
        )
        
        # Phase 1: Vote Phase - verify all participants are alive (gRPC)
        logger.info(f"Phase coordinator of Node {NODE_ID} starting vote phase for transaction {transaction_id}")
        all_votes_commit = True
        channels = []
        participants = []  # Store (node_type, node_id, channel) tuples
        
        # Vote with storage nodes
        for endpoint in STORAGE_NODES:
            node_id = endpoint.split(':')[0] if ':' in endpoint else endpoint
            channel = self._create_channel(endpoint)
            if not channel:
                all_votes_commit = False
                continue
            channels.append(channel)
            stub = twopc_pb2_grpc.VotePhaseServiceStub(channel)
            participants.append(('storage', node_id, channel))
            response = self._send_vote_request(stub, vote_request, node_id)
            if not response or not response.vote_commit:
                all_votes_commit = False
        
        # Vote with metadata nodes
        for endpoint in METADATA_NODES:
            node_id = endpoint.split(':')[0] if ':' in endpoint else endpoint
            channel = self._create_channel(endpoint)
            if not channel:
                all_votes_commit = False
                continue
            channels.append(channel)
            stub = twopc_pb2_grpc.VotePhaseServiceStub(channel)
            participants.append(('metadata', node_id, channel))
            response = self._send_vote_request(stub, vote_request, node_id)
            if not response or not response.vote_commit:
                all_votes_commit = False
        
        # Phase 2: Decision Phase
        logger.info(f"Phase coordinator of Node {NODE_ID} starting decision phase for transaction {transaction_id}")
        decision = all_votes_commit
        
        decision_request = twopc_pb2.DecisionRequest(
            transaction_id=transaction_id,
            global_commit=decision,
            node_id=NODE_ID
        )
        
        # Send decision to all participants (reuse existing channels)
        for node_type, node_id, channel in participants:
            decision_stub = twopc_pb2_grpc.DecisionPhaseServiceStub(channel)
            self._send_decision(decision_stub, decision_request, node_id)
        
        # Close channels
        for channel in channels:
            channel.close()
        
        # After 2PC decision: Operations are executed directly in participant's decision phase
        if decision:
            logger.info(f"Transaction {transaction_id} committed - all nodes validated and operations executed in decision phase")
            return {
                'success': True,
                'message': 'All nodes validated and operations executed',
                'transaction_id': transaction_id
            }
        else:
            logger.warning(f"Transaction {transaction_id} aborted - some nodes not alive")
            return {
                'success': False,
                'message': 'Some nodes not alive',
                'transaction_id': transaction_id
            }
