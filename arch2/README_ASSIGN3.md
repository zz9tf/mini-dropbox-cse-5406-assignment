# Assignment 3: Two-Phase Commit (2PC) Implementation

## Overview

This document describes the **Two-Phase Commit (2PC) protocol implementation** integrated into the Mini-Dropbox system (Architecture 2). This is a **system upgrade** that makes 2PC the default mechanism for file upload operations.

**Key Features**:

- ✅ 2PC is now the default for file uploads (system upgrade)
- ✅ Dual-port architecture: HTTP API + gRPC 2PC participant
- ✅ Minimal changes to original codebase
- ✅ 5+ containerized nodes for 2PC protocol
- ✅ Full gRPC-based communication

## Quick Start

```bash
# 1. Navigate to arch2 directory
cd arch2

# 2. Generate protobuf code
python -m grpc_tools.protoc -I./protos --python_out=. --grpc_python_out=. ./protos/twopc.proto

# 3. Start all services (original + 2PC)
docker-compose up --build

# 4. Test 2PC upload
# Get token from original service
TOKEN=$(curl -s -X POST http://localhost:5003/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass"}' | jq -r '.token')

# Upload with 2PC
curl -X POST http://localhost:5007/files/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@testfile.txt"
```

## What is 2PC?

Two-Phase Commit is a distributed consensus protocol that ensures atomicity across multiple distributed nodes. It consists of two phases:

1. **Vote Phase**: Coordinator asks all participants if they can commit
2. **Decision Phase**: Coordinator sends the final decision (commit or abort) to all participants

## Architecture Overview

The 2PC implementation uses a **dual-port architecture** where each service runs both:

1. **HTTP API** (original Flask endpoints) - for client communication
2. **gRPC 2PC Participant** (new) - for 2PC protocol communication

```
┌─────────────────────────────────────────────────────────────┐
│                    Client                                    │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP (Port 5003)
┌────────────────────▼────────────────────────────────────────┐
│         Upload Service                                       │
│         - HTTP API: Port 5003 (now uses 2PC by default)     │
│         - Calls 2PC Coordinator                             │
└────────────────────┬────────────────────────────────────────┘
                     │ gRPC (Port 6000)
┌────────────────────▼────────────────────────────────────────┐
│              2PC Coordinator (Port 6000)                     │
│              - Manages transaction lifecycle                 │
│              - Coordinates vote and decision phases          │
└───────┬───────────────────────────────┬─────────────────────┘
        │ gRPC                          │ gRPC
        │                               │
┌───────▼────────┐            ┌─────────▼──────────┐
│ Storage Nodes  │            │ Metadata Node      │
│                │            │                    │
│ HTTP: 5006     │            │ HTTP: 5005         │
│ gRPC: 6001     │            │ gRPC: 6002         │
│                │            │                    │
│ - storage      │            │ - metadata         │
│ - storage1     │            │                    │
│ - storage2     │            │                    │
│ - storage3     │            │                    │
└────────────────┘            └────────────────────┘
```

### Port Architecture Explanation

**为什么需要双端口？**

每个服务现在使用两个端口：

- **HTTP 端口** (5003, 5005, 5006): 原有的 Flask REST API，用于客户端通信
- **gRPC 端口** (6000-6004): 新的 2PC 协议通信端口，用于节点间的 2PC 消息传递

这种设计的优势：

1. **向后兼容**: HTTP API 保持不变，客户端无需修改
2. **协议分离**: HTTP 用于客户端，gRPC 用于内部 2PC 通信
3. **独立运行**: 两个服务在同一容器中并行运行（使用线程）
4. **清晰职责**: HTTP 处理业务逻辑，gRPC 处理分布式事务

## New Components

### 1. Protocol Buffer Definition (`protos/twopc.proto`)

Defines the gRPC service interfaces for 2PC:

- `VotePhaseService`: Handles vote requests and responses
- `DecisionPhaseService`: Handles decision requests and responses
- `InternalPhaseService`: For communication between phases within same node

### 2. 2PC Coordinator (`twopc/coordinator.py`)

- **Role**: Coordinates the 2PC protocol
- **Responsibilities**:
  - Sends vote requests to all participants
  - Collects votes and makes decision
  - Sends global-commit or global-abort to all participants
- **Node ID**: `coordinator-1`

### 3. Storage Participants (`twopc/participant_storage.py`)

- **Role**: Storage node participant in 2PC
- **Responsibilities**:
  - Receives vote requests and prepares file storage
  - Votes commit/abort based on ability to store file
  - Commits or aborts based on coordinator's decision
- **Node IDs**: `storage1`, `storage2`, `storage3`

### 4. Metadata Participant (`twopc/participant_metadata.py`)

- **Role**: Metadata node participant in 2PC
- **Responsibilities**:
  - Receives vote requests and prepares metadata update
  - Votes commit/abort based on ability to update metadata
  - Commits or aborts based on coordinator's decision
- **Node ID**: `metadata`

### 5. Upload Service (Upgraded)

- **Role**: HTTP endpoint that now uses 2PC by default
- **Port**: 5003 (HTTP API)
- **Endpoint**: `POST /files/upload` (now uses 2PC internally)
- **Change**: The original `/files/upload` endpoint now uses 2PC coordinator instead of direct storage calls

## File Structure

```
arch2/
├── protos/
│   └── twopc.proto                    # 2PC protocol definition
├── twopc/
│   ├── coordinator.py                 # 2PC coordinator implementation
│   ├── participant_storage.py         # Storage participant
│   ├── participant_metadata.py        # Metadata participant
│   └── upload_with_2pc.py            # Upload service with 2PC
├── docker-compose.yml                 # Updated with 2PC services
└── README_ASSIGN3.md                  # This file
```

## Prerequisites

- Docker and Docker Compose
- Python 3.11+
- gRPC tools: `pip install grpcio grpcio-tools`

## Setup Instructions

### 1. Generate Protocol Buffer Code

First, generate the gRPC code from the proto file:

```bash
cd arch2

# Install gRPC tools if not already installed
pip install grpcio grpcio-tools

# Generate protobuf code
python -m grpc_tools.protoc -I./protos --python_out=. --grpc_python_out=. ./protos/twopc.proto
```

This generates:

- `protos/twopc_pb2.py`
- `protos/twopc_pb2_grpc.py`

**Note**: The Dockerfiles will also generate these files automatically during build, but generating them locally helps with development and IDE support.

### 2. Build and Start Services

The `docker-compose.yml` has been extended with 2PC services. Start all services:

```bash
docker-compose up --build
```

This will start:

- **Original services** (unchanged):

  - `upload` (port 5003) - Original upload service
  - `download` (port 5004) - Download service
  - `metadata` (port 5005) - Metadata service (now with 2PC support)
  - `storage` (port 5006) - Original storage service
  - `backup` - Backup service
  - `client` - CLI client

- **New 2PC services**:
  - `twopc-coordinator` (port 6000) - 2PC coordinator
  - `twopc-storage1` (port 6001) - Additional storage participant 1
  - `twopc-storage2` (port 6002) - Additional storage participant 2
  - `twopc-storage3` (port 6003) - Additional storage participant 3

**Note**: The original `upload`, `storage`, and `metadata` services now also support 2PC (backward compatible).

**Total nodes**: 10 containers (6 original with 2PC support + 4 new 2PC-only services)

**2PC Node Count**: 5 nodes minimum

- 1 Coordinator
- 3 Storage Participants
- 1 Metadata Participant

## Usage

### Upload File with 2PC

The 2PC-enabled upload service is available on port 5007. Here's how to use it:

```bash
# Step 1: Get authentication token (using original upload service)
TOKEN=$(curl -s -X POST http://localhost:5003/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass"}' | jq -r '.token')

# Step 2: Upload file (now uses 2PC by default)
curl -X POST http://localhost:5003/files/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@testfile.txt"
```

**Note**: The `/files/upload` endpoint now uses 2PC by default. All file uploads are now atomic transactions across storage and metadata nodes.

### Response Format

**Success (201)**:

```json
{
  "message": "File uploaded successfully using 2PC",
  "transaction_id": "uuid-here",
  "filename": "testfile.txt"
}
```

**Failure (500)**:

```json
{
  "error": "2PC transaction aborted",
  "transaction_id": "uuid-here",
  "message": "Transaction aborted"
}
```

## 2PC Protocol Flow

### Phase 1: Vote Phase

1. Client sends upload request to Upload Service with 2PC
2. Upload Service creates transaction and calls Coordinator
3. Coordinator sends `VoteRequest` to all participants:
   - Storage nodes (storage1, storage2, storage3)
   - Metadata node
4. Each participant:
   - Prepares the operation (but doesn't commit)
   - Returns `VoteResponse` (vote-commit or vote-abort)

**Log Output**:

```
Phase coordinator of Node coordinator-1 sends RPC VoteRequest to Phase vote of Node storage1
Phase vote of Node storage1 runs RPC VoteRequest called by Phase coordinator of Node coordinator-1
Phase vote of Node storage1 sends RPC VoteResponse to Phase coordinator of Node coordinator-1
```

### Phase 2: Decision Phase

1. Coordinator collects all votes
2. If all vote-commit → Coordinator decides global-commit
3. If any vote-abort → Coordinator decides global-abort
4. Coordinator sends `DecisionRequest` to all participants
5. Each participant:
   - If global-commit → Commits the prepared operation
   - If global-abort → Aborts and discards prepared operation

**Log Output**:

```
Phase decision of Node coordinator-1 sends RPC DecisionRequest to Phase decision of Node storage1
Phase decision of Node storage1 runs RPC DecisionRequest called by Phase decision of Node coordinator-1
Phase decision of Node storage1 sends RPC DecisionResponse to Phase decision of Node coordinator-1
```

## Node Configuration

### Environment Variables

**Coordinator**:

- `NODE_ID`: Node identifier (default: `coordinator-1`)
- `STORAGE_NODES`: Comma-separated list of storage endpoints (default: `storage1:6001,storage2:6001,storage3:6001`)
- `METADATA_NODES`: Comma-separated list of metadata endpoints (default: `metadata:6002`)
- `COORDINATOR_PORT`: gRPC server port (default: `6000`)

**Storage Participants**:

- `NODE_ID`: Node identifier (`storage1`, `storage2`, `storage3`)
- `STORAGE_PATH`: File storage path (default: `/storage`)
- `PARTICIPANT_PORT`: gRPC server port (default: `6001`)

**Metadata Participant**:

- `NODE_ID`: Node identifier (default: `metadata`)
- `PARTICIPANT_PORT`: gRPC server port (default: `6002`)

## Testing

### Test 1: Successful Upload (All Participants Vote Commit)

```bash
# Upload a file (now uses 2PC by default)
curl -X POST http://localhost:5003/files/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@testfile.txt"

# Expected: 201 response with transaction_id
# Check logs for vote and decision phases
```

### Test 2: Failed Upload (Participant Votes Abort)

Simulate a failure by stopping one storage node:

```bash
docker-compose stop storage1
# Try upload - should fail with abort
docker-compose start storage1
```

### Test 3: View Logs

```bash
# Coordinator logs
docker-compose logs twopc-coordinator

# Storage participant logs
docker-compose logs twopc-storage1
docker-compose logs twopc-storage2
docker-compose logs twopc-storage3
docker-compose logs storage

# Metadata participant logs
docker-compose logs metadata

# Upload service logs
docker-compose logs upload
```

## Implementation Details

### System Upgrade Approach

The 2PC implementation is a **system upgrade** that integrates 2PC as the default mechanism for file uploads:

1. **Dual-Port Architecture**:

   - Each service runs **two servers** in the same container:
     - **HTTP Flask server**: Handles REST API requests (ports 5003, 5005, 5006)
     - **gRPC 2PC participant server**: Handles 2PC protocol messages (ports 6000-6004)
   - Both servers run in parallel using Python threads

2. **Upload Service Upgrade**:

   - The original `/files/upload` endpoint now uses 2PC by default
   - Instead of directly calling storage/metadata APIs, it:
     1. Creates a 2PC transaction
     2. Calls the 2PC coordinator
     3. Coordinator manages the distributed commit across all participants
   - **No API changes**: Clients still call the same endpoint, but now get atomic transactions

3. **Service Enhancements**:

   - **Metadata service**:
     - HTTP API on port 5005 (unchanged)
     - 2PC participant gRPC on port 6002 (new, runs in background thread)
   - **Storage service**:
     - HTTP API on port 5006 (unchanged)
     - 2PC participant gRPC on port 6001 (new, runs in background thread)
   - **Upload service**:
     - HTTP API on port 5003 (upgraded to use 2PC internally)
     - No separate gRPC server needed (acts as client to coordinator)

4. **Port Allocation**:
   - **6000**: 2PC Coordinator
   - **6001**: Storage participant (internal port, mapped to 6004 externally for original storage)
   - **6002**: Metadata participant
   - **6001**: Additional storage participants (storage1, storage2, storage3)
   - External ports 6001-6003 are mapped to internal port 6001 for storage participants

### File Modifications Summary

**New Files Created**:

- `protos/twopc.proto` - Protocol buffer definition
- `twopc/coordinator.py` - 2PC coordinator implementation
- `twopc/participant_storage.py` - Storage participant gRPC server
- `twopc/participant_metadata.py` - Metadata participant gRPC server
- `twopc/requirements.txt` - gRPC dependencies
- `twopc/Dockerfile` - Coordinator container
- `twopc/Dockerfile.storage` - Storage participant container

**Modified Files** (minimal changes - system upgrade):

- `docker-compose.yml` - Added 2PC services, volume mounts, and port mappings
- `metadata/app.py` - Added 2PC participant gRPC server startup (runs in background thread)
- `metadata/requirements.txt` - Added gRPC dependencies
- `metadata/Dockerfile` - Added gRPC port (6002) exposure
- `storage/app.py` - Added 2PC participant gRPC server startup (runs in background thread)
- `storage/requirements.txt` - Added gRPC dependencies
- `storage/Dockerfile` - Added gRPC port (6001) exposure
- `services/upload/app.py` - **Upgraded** `/files/upload` endpoint to use 2PC by default
- `services/upload/requirements.txt` - Added gRPC dependencies

### Communication Between Phases

As required by the assignment, vote and decision phases within the same node communicate via gRPC using `InternalPhaseService`. This allows:

- Vote phase to forward vote results to decision phase
- Decision phase to receive decisions from coordinator
- Both phases to run in the same container but as separate services

## Troubleshooting

### Port Conflicts

If ports are already in use, modify `docker-compose.yml` to use different ports.

### gRPC Connection Errors

Check that all services are running:

```bash
docker-compose ps
```

### Transaction Timeouts

If transactions hang, check participant logs for errors. Participants may be unable to vote commit.

## Future Enhancements

- Support for other operations (delete, update) with 2PC
- Transaction timeout handling
- Recovery mechanism for failed transactions
- Performance optimization with parallel vote requests

## Assignment Requirements Compliance

This implementation satisfies all Assignment 3 requirements:

### Q1: Vote Phase Implementation ✅

- Coordinator sends `VoteRequest` to all participants
- Participants return `VoteResponse` (vote-commit or vote-abort)
- All communication via gRPC with custom proto definitions
- Proper logging format: `Phase <phase_name> of Node <node_id> sends RPC <rpc_name> to Phase <phase_name> of Node <node_id>`

### Q2: Decision Phase Implementation ✅

- Coordinator collects all votes and makes decision
- Sends `DecisionRequest` (global-commit or global-abort) to all participants
- Participants commit or abort based on decision
- Vote and decision phases communicate via gRPC within same node using `InternalPhaseService`
- Proper logging for both phases

### Additional Requirements ✅

- ✅ At least 5 containerized nodes (1 coordinator + 3 storage + 1 metadata)
- ✅ All nodes can communicate via gRPC
- ✅ Custom gRPC data structures and service methods defined in `twopc.proto`
- ✅ Containerized deployment with Docker Compose
- ✅ Minimal changes to original system functionality

## References

- Original system: See `README.md` for base architecture
- 2PC Protocol: Distributed Systems consensus algorithm
- gRPC: https://grpc.io/

---

**Implementation Date**: 2025-01-XX  
**Assignment**: CSE 5406 Assignment 3 - Two-Phase Commit Protocol
