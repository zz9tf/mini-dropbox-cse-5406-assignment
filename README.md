# Mini-Dropbox - CSE 5406 Assignment 3: Two-Phase Commit (2PC)

This repository contains the implementation of **Two-Phase Commit (2PC) protocol** for the Mini-Dropbox distributed file storage system.

## ⚠️ Important: Assignment 3 Implementation

**The Assignment 3 (2PC) implementation is located in `arch2/` directory.**

All Assignment 3 related code, documentation, and tests are in the `arch2/` folder. This is the **latest and active** implementation for the 2PC protocol assignment.

## Quick Start

```bash
cd arch2
docker-compose up --build
./test_2pc.sh
```

## Assignment 3: 2PC Implementation Overview

The 2PC protocol ensures **atomicity** of file upload operations: files either succeed on both storage and metadata nodes simultaneously, or fail completely, preventing data inconsistency.

### Architecture

- **Upload Service** (Coordinator): Handles `/files/upload` endpoint and coordinates 2PC protocol
- **Storage Service** (Participant): Stores files, participates in 2PC via gRPC
- **Metadata Service** (Participant): Manages metadata, participates in 2PC via gRPC

**Dual-Port Design:**

- HTTP ports (5003, 5005, 5006): Client communication
- gRPC ports (6001, 6002): 2PC protocol communication

```
Client → Upload Service (Coordinator) → Storage + Metadata (Participants)
         HTTP:5003                    gRPC:6001, 6002
```

## Documentation

For detailed documentation, see:

- **[arch2/README_ASSIGN3.md](./arch2/README_ASSIGN3.md)** - Complete Assignment 3 documentation with usage, testing, and implementation details
- **[arch2/2PC_REPORT.md](./arch2/2PC_REPORT.md)** - Detailed implementation report covering:
  - Service architecture and 2PC functions
  - Complete pipeline workflow
  - Testing guide with all test cases
  - Response interpretation

## How to Run Assignment 3

### Prerequisites

- Docker and Docker Compose installed
- `jq` (optional, for JSON parsing in tests)

### Steps

1. **Navigate to arch2 directory:**

   ```bash
   cd arch2
   ```

2. **Start all services:**

   ```bash
   docker-compose up --build
   ```

3. **Run automated tests:**
   ```bash
   ./test_2pc.sh
   ```

### Manual Testing

**1. Sign up and login:**

```bash
curl -X POST http://localhost:5003/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass"}'

TOKEN=$(curl -s -X POST http://localhost:5003/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass"}' | jq -r '.token')
```

**2. Upload file (uses 2PC automatically):**

```bash
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

**3. View logs:**

```bash
# Coordinator logs
docker logs arch2-upload-1 | grep -E 'Phase|2PC|transaction'

# Storage participant logs
docker logs arch2-storage-1 | grep -E 'Phase|2PC|transaction|vote|decision'

# Metadata participant logs
docker logs arch2-metadata-1 | grep -E 'Phase|2PC|transaction|vote|decision'
```

## 2PC Protocol Flow

### Phase 1: Vote Phase

- Coordinator sends `VoteRequest` to all participants
- Participants prepare operations but **do not commit**
- Participants return `VoteResponse` (vote-commit or vote-abort)

### Phase 2: Decision Phase

- Coordinator collects votes and makes decision (global-commit or global-abort)
- Coordinator sends `DecisionRequest` to all participants
- Participants execute operations (save file/update metadata) or discard based on decision

**Key Point**: File saving and metadata updates happen **directly in the decision phase**, ensuring atomicity.

## Requirements Compliance

✅ **Vote Phase**: Coordinator sends VoteRequest, participants return VoteResponse  
✅ **Decision Phase**: Coordinator sends DecisionRequest, participants commit/abort  
✅ **gRPC Communication**: All 2PC messages via gRPC with custom proto  
✅ **Logging**: Proper log format for all RPC messages  
✅ **Atomicity**: Operations executed in decision phase  
✅ **Containerized**: Docker Compose deployment  
✅ **Minimal Changes**: Only upload function uses 2PC

## Project Structure

```
mini-dropbox-cse-5406-assignment/
├── arch2/                          # ⭐ Assignment 3 Implementation
│   ├── README_ASSIGN3.md          # Assignment 3 documentation
│   ├── 2PC_REPORT.md              # Detailed implementation report
│   ├── test_2pc.sh                # Automated test script
│   ├── protos/twopc.proto         # 2PC protocol definition
│   ├── services/upload/           # Upload service (Coordinator)
│   ├── storage/                   # Storage service (Participant)
│   ├── metadata/                  # Metadata service (Participant)
│   └── docker-compose.yml         # Service configuration
└── arch1/                          # Previous architecture (Assignment 2)
```

## Additional Notes

- The 2PC implementation is **backward compatible** - only `/files/upload` endpoint uses 2PC
- Other endpoints maintain original HTTP communication
- All services run both HTTP (client) and gRPC (2PC) servers simultaneously

---

**Assignment**: CSE 5406 Assignment 3 - Two-Phase Commit Protocol  
**Location**: `arch2/` directory
