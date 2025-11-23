# Assignment 3: Two-Phase Commit (2PC) Implementation

## Overview

This document describes the **Two-Phase Commit (2PC) protocol implementation** for the **file upload** operation in Mini-Dropbox (Architecture 2). The 2PC ensures atomicity: file uploads either succeed on both storage and metadata nodes, or fail completely.

## Quick Start

```bash
cd arch2
docker-compose up --build
./test_2pc.sh
```

## Architecture

The system uses a **dual-port architecture**:

- **HTTP ports** (5003, 5005, 5006): Original Flask REST API for clients
- **gRPC ports** (6001, 6002): 2PC protocol communication between nodes

```
Client → Upload Service (Coordinator) → Storage + Metadata (Participants)
         HTTP:5003                    gRPC:6001, 6002
```

**Components:**

- **Upload Service**: Contains 2PC coordinator, handles `/files/upload` endpoint
- **Storage Service**: 2PC participant (gRPC port 6001)
- **Metadata Service**: 2PC participant (gRPC port 6002)

## File Structure

```
arch2/
├── protos/twopc.proto                    # 2PC protocol definition
├── services/upload/
│   ├── app.py                            # Upload endpoint (uses 2PC)
│   └── twopc_coordinator.py              # 2PC coordinator
├── storage/
│   ├── app.py                            # Storage service
│   └── twopc_participant.py              # Storage participant
├── metadata/
│   ├── app.py                            # Metadata service
│   └── twopc_participant.py              # Metadata participant
├── test_2pc.sh                           # Automated test script
└── docker-compose.yml                    # Service configuration
```

## 2PC Protocol Flow

### Phase 1: Vote Phase

1. Coordinator sends `VoteRequest` to all participants (Storage and Metadata)
2. Each participant prepares the operation (decodes file data, parses metadata) but **does not commit**
3. Participants return `VoteResponse` (vote-commit or vote-abort)

**Log Example:**

```
Phase coordinator of Node coordinator sends RPC VoteRequest to Phase vote of Node storage
Phase vote of Node storage sends RPC VoteResponse to Phase coordinator of Node coordinator: Ready to commit (Vote: True)
```

### Phase 2: Decision Phase

1. Coordinator collects all votes
2. If all vote-commit → global-commit; if any vote-abort → global-abort
3. Coordinator sends `DecisionRequest` to all participants
4. Participants execute operation (save file or update metadata) if global-commit, or discard if global-abort

**Log Example:**

```
Phase decision of Node coordinator sends RPC DecisionRequest to Phase decision of Node storage
Phase decision of Node storage committed transaction xxx - file saved to /storage/testfile.txt
```

**Key Point**: File saving and metadata update happen **directly in the decision phase**, ensuring atomicity.

## Usage

**Upload file (uses 2PC automatically):**

```bash
# 1. Sign up and login
curl -X POST http://localhost:5003/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass"}'

TOKEN=$(curl -s -X POST http://localhost:5003/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass"}' | jq -r '.token')

# 2. Upload file (2PC is used automatically)
curl -X POST http://localhost:5003/files/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@testfile.txt"
```

**Success Response (201):**

```json
{
  "message": "File uploaded successfully using 2PC",
  "transaction_id": "uuid-here",
  "filename": "testfile.txt",
  "path": "/storage/testfile.txt"
}
```

**Failure Response (500):**

```json
{
  "error": "2PC transaction failed",
  "message": "Some nodes not alive",
  "transaction_id": "uuid-here"
}
```

## Testing

**Automated tests:**

```bash
./test_2pc.sh
```

The test script includes:

- Test Case 1: Normal upload with all nodes alive
- Test Case 2: Verify file was saved in storage
- Test Case 3: Verify metadata was updated
- Test Case 4: Upload with storage node down (should abort)
- Test Case 5: Upload with metadata node down (should abort)
- Test Case 6: Verify RPC messages in logs

## Implementation Details

### System Upgrade

- **Minimal changes**: Only `/files/upload` endpoint uses 2PC
- **Dual-port**: Each service runs HTTP (client) + gRPC (2PC) servers
- **Backward compatible**: Other endpoints unchanged

### Modified Files

**New:**

- `protos/twopc.proto` - Protocol definition
- `services/upload/twopc_coordinator.py` - Coordinator
- `storage/twopc_participant.py` - Storage participant
- `metadata/twopc_participant.py` - Metadata participant

**Modified:**

- `services/upload/app.py` - `/files/upload` uses 2PC
- `storage/app.py` - Added gRPC participant server
- `metadata/app.py` - Added gRPC participant server
- `docker-compose.yml` - Added gRPC ports and protos mount

## Requirements Compliance

✅ **Vote Phase**: Coordinator sends VoteRequest, participants return VoteResponse  
✅ **Decision Phase**: Coordinator sends DecisionRequest, participants commit/abort  
✅ **gRPC Communication**: All 2PC messages via gRPC with custom proto  
✅ **Logging**: Proper log format for all RPC messages  
✅ **Atomicity**: Operations executed in decision phase  
✅ **Containerized**: Docker Compose deployment  
✅ **Minimal Changes**: Only upload function uses 2PC

## Additional Documentation

For detailed implementation report, see [2PC_REPORT.md](./2PC_REPORT.md)

---

**Assignment**: CSE 5406 Assignment 3 - Two-Phase Commit Protocol
