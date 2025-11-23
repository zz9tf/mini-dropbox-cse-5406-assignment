# Architecture 2 - Microservices Architecture

This architecture decomposes Mini-Dropbox into smaller, independently deployable services: upload, download, metadata, storage, backup, and client. It demonstrates a modern microservices approach to distributed file storage and management.

## Overview

- **Client Service:** CLI interface for users (signup, login, upload, download, delete, list).
- **Upload/Download Services:** Handle file upload and download endpoints, interacting with metadata and storage.
- **Metadata Service:** Centralized file metadata database.
- **Storage Service:** File I/O and persistence.
- **Backup Service:** Periodic backup of metadata and stored files.


## Capabilities

- User management and JWT-based authentication.
- File upload/download, deletion, and listing, with permission checks.
- Metadata versioning and file tracking.
- Extensible multi-service deployment for scalability.
- Automated periodic backup.
- Docker Compose for easy orchestration.

## How to Run

1. Start all services:
   ```
   docker-compose up
   ```
2. Enter the client server:
   ```
   docker-compose run client /bin/bash
   ```
3. Use the CLI:
   ```
   python cli.py signup username password
   python cli.py login username password
   python cli.py upload somefile.txt
   python cli.py download somefile.txt
   python cli.py delete somefile.txt
   python cli.py list
   ```
4. (Optional) Inspect stored files:
   ```
   docker exec -it arch2-storage-1 sh
   ls /storage
   ```

## Assumptions & Notes

- Minimal error handling; intended for concept demonstration.
- Service ports: 5003 (upload), 5004 (download), 5005 (metadata), 5006 (storage), .
- For more details or to compare architectures, see the main [README](../README.md).

---

_This architecture is part of the Mini-Dropbox CSE 5406-004 project._