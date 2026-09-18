# Enterprise-RAG-Platform

A production-oriented, multi-tenant AI knowledge platform that enables organizations to securely upload, manage, search, and interact with their private knowledge using Retrieval-Augmented Generation (RAG).

Enterprise-RAG-Platform is a full-stack AI platform designed to transform an organization's internal documents and knowledge into an intelligent, searchable, conversational knowledge system.

Instead of building a basic:

`PDF → Embeddings → Vector Database → LLM`

pipeline, this project focuses on the engineering required to turn RAG into a reliable application:

Authentication ↓ Organizations / Workspaces ↓ Document Management ↓ Asynchronous Ingestion ↓ Document Parsing ↓ Chunking ↓ Embeddings ↓ Hybrid Retrieval ↓ Reranking ↓ Context Construction ↓ LLM Generation ↓ Streaming Response ↓ Citations + Conversation History ↓ Usage Tracking + Monitoring

The platform is designed with security, scalability, observability, reliability, maintainability, and AI evaluation as first-class concerns.

## Table of Contents
* [Overview](#overview)
* [Problem Statement](#problem-statement)
* [Solution](#solution)
* [Why This Project Exists](#why-this-project-exists)
* [What the Platform Does](#what-the-platform-does)
* [Core Features](#core-features)
* [Architecture](#architecture)
* [Deployment](#deployment)
* [CI/CD](#cicd)
* [Testing](#testing)
* [Future Improvements](#future-improvements)
* [Roadmap](#roadmap)
* [License](#license)

*(And more...)*

## Overview
Modern organizations generate enormous amounts of information:
* PDFs
* Word documents
* technical documentation
* employee handbooks
* product manuals
* policies
* legal documents
* research reports
* support documentation
* internal wikis
* compliance documents
* engineering documentation
* knowledge bases

Traditional document search generally depends heavily on keywords.
An employee may know what they want to ask but not know the exact terminology used in the source document.

For example:
User: "How many days can I work remotely?"
The document may contain:
"Employees are permitted to work from an alternative location for a maximum of three working days per week."

A semantic retrieval system can understand that these statements are related even though the wording is different.

Enterprise-RAG-Platform combines:
Semantic Search + Keyword Search + Reranking + LLM Generation + Citations + Access Control + Document Management + Observability
to provide an organization-specific AI knowledge system.

## Problem Statement
Organizations often have their knowledge distributed across:
Shared drives, PDFs, DOCX files, Web pages, Internal documentation, Databases, Knowledge bases, Cloud storage.

Employees may spend significant time searching through these resources.
Traditional approaches create several problems:
1. **Information fragmentation**: Knowledge exists across many locations.
2. **Keyword dependency**: Users must know the terminology used by the original documents.
3. **Information retrieval overhead**: Finding the correct document and section can be time-consuming.
4. **Lack of conversational interaction**: Traditional search returns documents instead of directly answering questions.
5. **Knowledge accessibility**: New employees may not know where information is stored.
6. **Verification**: AI-generated answers without sources are difficult to trust.
7. **Security**: Organizations cannot simply expose all internal documents to every employee.
8. **Scalability**: Manually processing and indexing thousands of documents is impractical.

Enterprise-RAG-Platform is designed to address these engineering and usability challenges.

## Solution
The platform provides a centralized knowledge layer.

`Organization ↓ Upload Knowledge ↓ Automatically Process Documents ↓ Create Searchable Knowledge Index ↓ Ask Natural-Language Questions ↓ Retrieve Relevant Information ↓ Rank Relevant Sources ↓ Generate Grounded Answer ↓ Show Citations`

The system does not require the organization to retrain an LLM every time a document changes.
Instead, organizational knowledge is maintained through the retrieval layer.
This allows the knowledge base to be updated independently from the underlying language model.

## Why This Project Exists
A basic RAG application demonstrates:
"I know how to connect an LLM to a vector database."

This project aims to demonstrate much more:
"I can design and engineer an AI system as a complete software product."

It combines:
* **Artificial Intelligence**: LLMs, embeddings, semantic search, RAG, reranking, query rewriting, evaluation
* **Backend Engineering**: REST APIs, authentication, authorization, asynchronous processing, streaming, validation, error handling
* **Database Engineering**: PostgreSQL, relational modeling, indexes, transactions, vector databases, caching
* **Distributed Systems**: background workers, message queues, retries, idempotency, fault tolerance
* **DevOps**: Docker, CI/CD, cloud deployment, monitoring, logging
* **System Design**: multi-tenancy, scalability, service boundaries, data isolation, observability, reliability

## What the Platform Does
The platform provides a complete lifecycle for organizational knowledge.
1. User registers 
2. Organization is created 
3. Workspace is created 
4. Documents are uploaded 
5. Documents are stored 
6. Background workers process them 
7. Text is extracted 
8. Text is chunked 
9. Chunks are embedded 
10. Vectors are indexed 
11. User asks a question 
12. Relevant information is retrieved 
13. Results are reranked 
14. LLM generates grounded response 
15. Sources are attached 
16. Response is streamed 
17. Conversation is stored 
18. Usage is recorded

## Core Features
* **Authentication**: Registration, Login, Logout, JWT authentication, Token refresh, Password hashing, User profile, Session management
* **Organizations**: The platform supports organization-level isolation.
* **Workspaces**: Organizations can divide knowledge into logical workspaces (e.g., Engineering, Human Resources).
* **Document Management**: Supported document types include PDF, DOCX, HTML, TXT, Markdown.
* **Semantic Search**: Documents are transformed into vector representations using embedding models.
* **Hybrid Search**: Combines Semantic Search + Keyword Search.
* **Reranking**: A reranker evaluates the relationship between Question + Candidate Chunk and produces a more accurate relevance ordering.
* **Retrieval-Augmented Generation (RAG)**: The system retrieves relevant organizational knowledge to provide context to the LLM.
* **Citation Generation**: Answers are traceable back to the source material.
* **Conversation History**: Persistent conversations with context awareness.
* **Streaming Responses**: Progressive token streaming for better responsiveness.
* **Multi-Tenancy**: Logical data isolation across multiple organizations on the same platform instance.
* **Authentication and Authorization**: Role-based access control (Admin, Member, Viewer).
* **Asynchronous Document Processing**: Background workers for computationally expensive ingestion.
* **Caching & Rate Limiting**: Redis-backed caching and API usage limits.
* **Usage Tracking**: Records tokens, latency, and estimated costs.
* **Admin Dashboard**: System monitoring and analytics.

## Architecture
**High-level architecture:**
```
USERS 
  ▼
React / Next.js Frontend
  ▼
API Gateway / Proxy
  ▼
FastAPI Backend Platform
  ├── PostgreSQL (Application Data)
  ├── Redis (Cache / Rate Limits)
  ├── S3 (Documents)
  ├── Celery / Workers (Background Tasks)
  ├── RabbitMQ (Message Queue)
  └── Qdrant (Vector Database)
```

## Setup & Installation

### Prerequisites
* Python 3.11+
* Node.js 20+
* Docker & Docker Compose
* Git

### Installation
Clone the repository:
```bash
git clone https://github.com/<your-username>/Enterprise-RAG-Platform.git
cd Enterprise-RAG-Platform
```

#### Backend Setup
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
pip install -r backend/requirements.txt
```

#### Frontend Setup
```bash
cd frontend
npm install
cd ..
```

#### Infrastructure Setup
Start local infrastructure:
```bash
docker compose up -d
```
Expected services: PostgreSQL, Redis, RabbitMQ, Qdrant, MinIO.

## Roadmap

### Phase 1 — Foundation
* [x] Project structure
* [ ] FastAPI setup
* [ ] PostgreSQL setup
* [ ] Basic authentication

### Phase 2 — RAG
* [ ] PDF ingestion
* [ ] Text extraction
* [ ] Chunking
* [ ] Embeddings
* [ ] Qdrant
* [ ] Basic retrieval
* [ ] LLM generation

### Phase 3 — Enterprise Features
* [ ] Organizations
* [ ] Workspaces
* [ ] RBAC
* [ ] Multi-tenancy
* [ ] Document management
* [ ] Document versioning

### Phase 4 — Advanced RAG
* [ ] Hybrid retrieval
* [ ] Reranking
* [ ] Query rewriting
* [ ] Citations
* [ ] Conversational RAG
* [ ] Streaming

### Phase 5 — Infrastructure
* [ ] Redis
* [ ] Celery
* [ ] RabbitMQ
* [ ] S3
* [ ] Background ingestion
* [ ] Retry mechanisms

### Phase 6 — Production Engineering
* [ ] Rate limiting
* [ ] Usage tracking
* [ ] Security hardening
* [ ] Logging
* [ ] Monitoring
* [ ] Distributed tracing

### Phase 7 — Evaluation
* [ ] Evaluation dataset
* [ ] Recall@K
* [ ] MRR
* [ ] nDCG
* [ ] Faithfulness
* [ ] Citation evaluation

### Phase 8 — Deployment
* [ ] Docker
* [ ] CI/CD
* [ ] AWS deployment
* [ ] Production monitoring
* [ ] Load testing

## License
This project is intended for educational, research, and portfolio purposes unless a different license is specified.
