# Two-Phase Commit (2PC) Implementation Report

## 1. Overview: Adding 2PC Support to Upload Functionality

This report details the implementation of the **Two-Phase Commit (2PC) protocol** in the Upload functionality of the Mini-Dropbox system. The 2PC ensures **atomicity** of file upload operations: files either succeed on both storage and metadata nodes simultaneously, or fail completely, preventing data inconsistency issues.

### 1.1 Existing Service Architecture

The system uses a microservices architecture with the following core services:

#### 1.1.1 Upload Service

- **Port**: HTTP 5003
- **Function**: Handles client file upload requests
- **Responsibilities**:
  - Receives file uploads from clients
  - Coordinates storage and metadata services to complete upload operations
  - **New**: Acts as the 2PC protocol coordinator

#### 1.1.2 Storage Service

- **Ports**: HTTP 5006, gRPC 6001
- **Function**: Physical file storage
- **Responsibilities**:
  - Saves files to local filesystem (`/storage`)
  - Provides HTTP APIs for file upload, download, and delete
  - **New**: Acts as a 2PC protocol participant, executing file save operations in the decision phase

#### 1.1.3 Metadata Service

- **Ports**: HTTP 5005, gRPC 6002
- **Function**: File metadata management
- **Responsibilities**:
  - Stores file metadata (filename, path, size, version, etc.)
  - Provides HTTP APIs for metadata CRUD operations
  - **New**: Acts as a 2PC protocol participant, updating metadata in the decision phase

#### 1.1.4 Other Services

- **Download Service**: Handles file download requests
- **Backup Service**: Periodically backs up metadata and files
- **Client**: CLI client tool

### 1.2 How Upload Functionality Uses Existing Services

#### Original Implementation (without 2PC)

```
Client → Upload Service (HTTP 5003)
          ↓ HTTP POST /upload
          Storage Service (HTTP 5006) → Save file
          ↓ HTTP POST /files
          Metadata Service (HTTP 5005) → Update metadata
```

**Problem**: If Storage Service succeeds but Metadata Service fails, data inconsistency occurs (file saved but metadata not updated).

#### After 2PC Implementation

```
Client → Upload Service (Coordinator, HTTP 5003)
          ↓ 2PC Protocol (gRPC)
          ├─→ Storage Service (Participant, gRPC 6001)
          └─→ Metadata Service (Participant, gRPC 6002)
```

**Advantage**: The 2PC protocol ensures all nodes either commit together or rollback together, guaranteeing atomicity.

### 1.3 2PC Functions Added to Each Service

#### 1.3.1 Upload Service - Coordinator

**New File**: `services/upload/twopc_coordinator.py`

**Core Functions**:

1. **`TwoPhaseCommitCoordinator` Class**

   - Manages 2PC transaction lifecycle
   - Generates unique transaction IDs (UUID)

2. **`execute_2pc_upload()` Method**

   - Executes the complete 2PC flow
   - Phase 1 (Vote Phase): Sends `VoteRequest` to all participants
   - Phase 2 (Decision Phase): Sends `DecisionRequest` based on vote results

3. **`_send_vote_request()` Method**

   - Sends vote requests to participants via gRPC
   - Logs: `"Phase coordinator of Node {coordinator} sends RPC VoteRequest to Phase vote of Node {participant}"`
   - Receives and processes `VoteResponse`

4. **`_send_decision()` Method**
   - Sends decision requests to participants via gRPC
   - Logs: `"Phase decision of Node {coordinator} sends RPC DecisionRequest to Phase decision of Node {participant}"`
   - Receives and processes `DecisionResponse`

**Modified File**: `services/upload/app.py`

- The `/files/upload` endpoint now calls `TwoPhaseCommitCoordinator.execute_2pc_upload()`
- Returns response containing `transaction_id` to identify the 2PC transaction

#### 1.3.2 Storage Service - Participant

**New File**: `storage/twopc_participant.py`

**Core Functions**:

1. **`StorageVotePhaseService` Class** (Vote Phase)

   - Implements `Vote()` RPC method
   - **Function**: Receives `VoteRequest`, prepares file data (decodes base64, validates path) but **does not save the file**
   - Stores transaction information in `pending_transactions` dictionary
   - Returns `VoteResponse(vote_commit=True)` indicating readiness

2. **`StorageDecisionPhaseService` Class** (Decision Phase)
   - Implements `Decision()` RPC method
   - **Function**:
     - If `global_commit=True`: **Actually saves the file** to `/storage/{filename}`
     - If `global_commit=False`: Discards prepared transaction data
   - Logs: `"Phase decision of Node storage committed transaction {id} - file saved to {path}"`

**Modified File**: `storage/app.py`

- Starts gRPC server in background thread (port 6001)
- Runs both HTTP server (port 5006) and gRPC server simultaneously

#### 1.3.3 Metadata Service - Participant

**New File**: `metadata/twopc_participant.py`

**Core Functions**:

1. **`MetadataVotePhaseService` Class** (Vote Phase)

   - Implements `Vote()` RPC method
   - **Function**: Receives `VoteRequest`, parses metadata JSON but **does not update FILES dictionary**
   - Stores transaction information in `pending_transactions` dictionary
   - Returns `VoteResponse(vote_commit=True)` indicating readiness

2. **`MetadataDecisionPhaseService` Class** (Decision Phase)
   - Implements `Decision()` RPC method
   - **Function**:
     - If `global_commit=True`: **Actually updates FILES dictionary** (metadata store)
     - If `global_commit=False`: Discards prepared transaction data
   - Logs: `"Phase decision of Node metadata committed transaction {id} - metadata updated for {filename}"`

**Modified File**: `metadata/app.py`

- Starts gRPC server in background thread (port 6002)
- Passes reference to `FILES` dictionary to `twopc_participant.serve()`, enabling direct metadata updates in decision phase
- Runs both HTTP server (port 5005) and gRPC server simultaneously

#### 1.3.4 Protocol Definition

**New File**: `protos/twopc.proto`

Defines gRPC service interfaces for 2PC protocol:

- **VotePhaseService**: `Vote(VoteRequest) returns (VoteResponse)`
- **DecisionPhaseService**: `Decision(DecisionRequest) returns (DecisionResponse)`

Message types include:

- `VoteRequest`: Contains transaction ID, operation type, filename, file data (base64), metadata JSON
- `VoteResponse`: Contains vote result (vote_commit), message, node ID
- `DecisionRequest`: Contains transaction ID, global decision (global_commit), node ID
- `DecisionResponse`: Contains execution result (success), message, node ID

## 2. 2PC Pipeline Workflow

### 2.1 Complete Flow Overview

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTP POST /files/upload
       │ (file + auth token)
       ▼
┌─────────────────────────────────────┐
│   Upload Service (Coordinator)      │
│   - Receives file upload request    │
│   - Generates transaction_id         │
│   - Calls execute_2pc_upload()      │
└──────┬──────────────────────────────┘
       │
       │ Phase 1: Vote Phase
       │
       ├─────────────────┬─────────────────┐
       │                 │                 │
       ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Storage    │  │   Metadata   │  │  (Extensible)│
│  Participant │  │  Participant │  │              │
│              │  │              │  │              │
│ VoteRequest  │  │ VoteRequest  │  │              │
│     ↓        │  │     ↓        │  │              │
│ Prepare file │  │ Prepare      │  │              │
│ data (no     │  │ metadata     │  │              │
│ save)        │  │ (no update)  │  │              │
│     ↓        │  │     ↓        │  │              │
│ VoteResponse │  │ VoteResponse │  │              │
│ (vote_commit)│  │ (vote_commit)│  │              │
└──────┬───────┘  └──────┬───────┘  └──────────────┘
       │                 │
       └────────┬────────┘
                │
                ▼
       ┌─────────────────┐
       │  Coordinator    │
       │  Collects votes │
       │  Decision:      │
       │  - All pass →   │
       │    global_commit│
       │  - Any fail →   │
       │    global_abort │
       └────────┬────────┘
                │
                │ Phase 2: Decision Phase
                │
       ┌────────┴────────┐
       │                 │
       ▼                 ▼
┌──────────────┐  ┌──────────────┐
│   Storage    │  │   Metadata   │
│  Participant │  │  Participant │
│              │  │              │
│DecisionRequest│ │DecisionRequest│
│     ↓        │  │     ↓        │
│ If commit:   │  │ If commit:   │
│ Save file    │  │ Update       │
│ If abort:    │  │ metadata     │
│ Discard data │  │ If abort:    │
│     ↓        │  │ Discard data │
│DecisionResponse││DecisionResponse│
└──────────────┘  └──────────────┘
```

### 2.2 Phase 1: Vote Phase

**Objective**: Verify all participant nodes are alive and prepare operations (but do not execute)

**Detailed Steps**:

1. **Coordinator Initiates Voting**

   ```python
   # Upload Service (Coordinator)
   vote_request = VoteRequest(
       transaction_id="uuid-xxx",
       operation="upload",
       filename="test.txt",
       file_data=base64_encoded_data,
       metadata_json=json_metadata
   )
   ```

2. **Send VoteRequest to Storage Participant**

   - Storage receives request
   - Decodes base64 file data
   - Validates file path
   - **Does not save file**, only stores data in `pending_transactions[transaction_id]`
   - Returns `VoteResponse(vote_commit=True, message="Ready to commit")`

3. **Send VoteRequest to Metadata Participant**

   - Metadata receives request
   - Parses JSON metadata
   - **Does not update FILES dictionary**, only stores data in `pending_transactions[transaction_id]`
   - Returns `VoteResponse(vote_commit=True, message="Ready to commit")`

4. **Coordinator Collects Votes**
   - If all participants return `vote_commit=True` → Proceed to Decision Phase with `global_commit=True`
   - If any participant returns `vote_commit=False` or connection fails → Proceed to Decision Phase with `global_commit=False`

**Log Example**:

```
Phase coordinator of Node coordinator sends RPC VoteRequest to Phase vote of Node storage
Phase vote of Node storage runs RPC VoteRequest called by Phase coordinator of Node coordinator
Phase vote of Node storage sends RPC VoteResponse to Phase coordinator of Node coordinator: Ready to commit (Vote: True)
```

### 2.3 Phase 2: Decision Phase

**Objective**: Based on vote results, notify all participants to execute or rollback operations

**Detailed Steps**:

1. **Coordinator Sends Decision**

   ```python
   # Upload Service (Coordinator)
   decision_request = DecisionRequest(
       transaction_id="uuid-xxx",
       global_commit=True/False,  # Determined by vote results
       node_id="coordinator"
   )
   ```

2. **Storage Participant Executes Decision**

   - If `global_commit=True`:
     - Retrieves prepared file data from `pending_transactions[transaction_id]`
     - **Actually saves file** to `/storage/{filename}`
     - Removes pending transaction
     - Returns `DecisionResponse(success=True, message="Transaction committed")`
   - If `global_commit=False`:
     - Removes pending transaction (discards prepared data)
     - Returns `DecisionResponse(success=True, message="Transaction aborted")`

3. **Metadata Participant Executes Decision**

   - If `global_commit=True`:
     - Retrieves prepared metadata from `pending_transactions[transaction_id]`
     - **Actually updates FILES dictionary** (`FILES[filename] = metadata`)
     - Removes pending transaction
     - Returns `DecisionResponse(success=True, message="Transaction committed")`
   - If `global_commit=False`:
     - Removes pending transaction (discards prepared data)
     - Returns `DecisionResponse(success=True, message="Transaction aborted")`

4. **Coordinator Returns Result to Client**
   - If all participants successfully commit → Returns HTTP 201 with `transaction_id`
   - If any participant fails or decision is abort → Returns HTTP 500 with error message

**Log Example**:

```
Phase decision of Node coordinator sends RPC DecisionRequest to Phase decision of Node storage
Phase decision of Node storage runs RPC DecisionRequest called by Phase decision of Node coordinator
Phase decision of Node storage committed transaction uuid-xxx - file saved to /storage/test.txt
Phase decision of Node storage sends RPC DecisionResponse to Phase decision of Node coordinator: Transaction committed (Success: True)
```

### 2.4 Key Design Points

1. **Atomicity Guarantee**: File saving and metadata updates both execute in Decision Phase, ensuring all-or-nothing behavior
2. **Dual-Port Architecture**: Each service runs both HTTP server (client communication) and gRPC server (2PC protocol communication)
3. **Backward Compatibility**: Only `/files/upload` endpoint uses 2PC, other endpoints maintain original HTTP call pattern
4. **Fault Handling**: If any participant is unreachable in Vote Phase, Coordinator receives exception and decision becomes `global_abort`

## 3. 2PC Testing Guide

### 3.1 Test Script

Test Script: `test_2pc.sh`

This script automates multiple test cases to verify the correctness of the 2PC implementation.

### 3.2 Detailed Test Cases

#### Test Case 1: Normal Upload - All Nodes Alive

**Test Content**:

1. Register user `testuser`
2. Login to get JWT token
3. Upload test file `test_file_2pc.txt`

**Expected Result**:

- HTTP Status Code: 201
- Response contains:
  ```json
  {
    "message": "File uploaded successfully using 2PC",
    "transaction_id": "uuid-xxx",
    "filename": "test_file_2pc.txt",
    "path": "/storage/test_file_2pc.txt"
  }
  ```

**How to Understand**:

- `transaction_id` indicates 2PC protocol was used
- File should be saved in both Storage and Metadata
- All participants should return `vote_commit=True`, final decision is `global_commit=True`

#### Test Case 2: Verify File Was Saved

**Test Content**:

- Check via Docker exec if file exists in Storage container's `/storage` directory

**Expected Result**:

- File `test_file_2pc.txt` exists at `/storage/test_file_2pc.txt`
- File content is correct

**How to Understand**:

- Verifies Storage Participant successfully executed file save in Decision Phase
- If file doesn't exist, 2PC Decision Phase was not executed correctly

#### Test Case 3: Verify Metadata Was Updated

**Test Content**:

1. Wait for 2PC transaction to complete (sleep 2 seconds)
2. Query Metadata Service for file list
3. Check logs for metadata update records

**Expected Result**:

- File `test_file_2pc.txt` appears in metadata query results
- Or logs contain: `"committed transaction {id} - metadata updated for test_file_2pc.txt"`

**How to Understand**:

- Verifies Metadata Participant successfully updated FILES dictionary in Decision Phase
- If metadata not updated, 2PC atomicity was not guaranteed

#### Test Case 4: Storage Node Failure Test

**Test Content**:

1. Stop Storage container
2. Attempt to upload file
3. Restart Storage container

**Expected Result**:

- HTTP Status Code: 500
- Response contains:
  ```json
  {
    "error": "2PC transaction failed",
    "message": "Some nodes not alive",
    "transaction_id": "uuid-xxx"
  }
  ```

**How to Understand**:

- Coordinator cannot connect to Storage Participant in Vote Phase
- Receives RPC exception, decision becomes `global_abort`
- File is not saved, metadata is not updated (atomicity guarantee)
- This verifies 2PC's fault tolerance capability

#### Test Case 5: Metadata Node Failure Test

**Test Content**:

1. Stop Metadata container
2. Attempt to upload file
3. Restart Metadata container

**Expected Result**:

- Same as Test Case 4, transaction is aborted

**How to Understand**:

- Verifies that when any participant is unavailable, entire transaction rolls back
- Ensures no partial commits occur

#### Test Case 6: Verify RPC Messages in Logs

**Test Content**:

- Check service logs for 2PC-related RPC messages

**Expected Result**:

- Coordinator logs contain:
  - `"sends RPC VoteRequest"`
  - `"sends RPC DecisionRequest"`
- Participant logs contain:
  - `"runs RPC VoteRequest"`
  - `"runs RPC DecisionRequest"`
  - `"committed transaction"` or `"aborted transaction"`

**How to Understand**:

- Log format meets assignment requirements, clearly showing both phases of 2PC
- Can trace entire transaction execution through logs

### 3.3 Test Response Interpretation

#### Success Response (201)

```json
{
  "message": "File uploaded successfully using 2PC",
  "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "test_file_2pc.txt",
  "path": "/storage/test_file_2pc.txt"
}
```

**Field Descriptions**:

- `message`: Indicates 2PC protocol was used
- `transaction_id`: Uniquely identifies this 2PC transaction, can be used for log tracing
- `filename`: Uploaded filename
- `path`: File save path

#### Failure Response (500)

```json
{
  "error": "2PC transaction failed",
  "message": "Some nodes not alive",
  "transaction_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Field Descriptions**:

- `error`: Error type
- `message`: Specific error reason (node unreachable, vote failed, etc.)
- `transaction_id`: Even on failure, transaction ID is generated for debugging

### 3.4 How to Run Tests

```bash
cd arch2
docker-compose up --build
./test_2pc.sh
```
