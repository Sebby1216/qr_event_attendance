# Attendance System with QR Code Check-in

## Overview

This is a barebones student attendance tracking system built with Python FastAPI and vanilla HTML/JavaScript. The application allows administrators to register students, generate QR codes containing student information, and enables students to check in by scanning their QR codes using a device camera. The system provides a live view of attendance records grouped by year, program, and section.

**Status**: Fully implemented and tested (October 22, 2025)
- QR code generation and parsing working correctly with exact format: "Sebastian Maurice L. Tadeo BSIT 3A"
- Duplicate detection prevents same-day check-ins
- Live attendance view displays hierarchical data (Year → Program → Section)
- All endpoints functional and tested

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Backend Architecture

**Framework**: FastAPI
- **Rationale**: Lightweight, modern Python web framework with built-in async support and automatic API documentation
- **Pros**: Fast development, minimal boilerplate, easy to understand
- **Cons**: Less feature-rich than full frameworks like Django

**ORM Layer**: SQLAlchemy
- **Problem**: Need to interact with database using Python objects rather than raw SQL
- **Solution**: SQLAlchemy ORM with declarative base for model definitions
- **Pros**: Type-safe, prevents SQL injection, easier to maintain
- **Cons**: Additional abstraction layer adds slight complexity

### Data Storage

**Database**: SQLite
- **Problem**: Simple data persistence without infrastructure overhead
- **Solution**: SQLite with file-based storage (attendance.db)
- **Pros**: Zero configuration, serverless, perfect for single-event tracking
- **Cons**: Not suitable for high-concurrency scenarios

**Data Model**:
- `students` table: Stores unique student records with composite unique constraint on (first_name, middle, last_name, program, year, section)
- `attendance` table: Records check-in timestamps with foreign key to students, unique constraint prevents duplicate daily check-ins
- Relationship: One-to-many from students to attendance records

### Frontend Architecture

**Technology Stack**: Vanilla HTML/JavaScript
- **Rationale**: Minimal dependencies, no build process required
- **Pros**: Simple, fast loading, no framework overhead
- **Cons**: More manual DOM manipulation

**QR Code Scanning**: jsQR library
- **Problem**: Need to decode QR codes from camera feed in browser
- **Solution**: Client-side JavaScript library for real-time QR detection
- **Implementation**: Uses getUserMedia API for camera access, canvas for frame processing

**Live Updates**: Polling mechanism
- **Problem**: Display real-time attendance without WebSocket complexity
- **Solution**: Simple HTTP polling every 2-3 seconds
- **Alternatives**: Server-Sent Events (SSE) mentioned as option
- **Pros**: Simple to implement, works everywhere
- **Cons**: Less efficient than push-based approaches

### QR Code Generation

**Library**: Python qrcode library
- **Problem**: Generate downloadable QR codes for each student
- **Solution**: Server-side QR generation with in-memory image streaming
- **Format**: Plain text string format: "FirstName Middle LastName Program YearSection"
- **Example**: "Sebastian Maurice L. Tadeo BSIT 3A"

### QR Text Parsing Strategy

**Format Requirements**: Strict regex-based parsing
- **Pattern**: Last token is YearSection (1 digit + 1 letter), second-to-last is Program (2-10 uppercase letters)
- **Name Extraction**: Remaining tokens form name (first token = FirstName, last = LastName, middle tokens = Middle)
- **Validation**: Returns 400 error if parsing fails
- **Rationale**: Ensures data integrity without requiring additional metadata

### Student Upsert Logic

**Approach**: Automatic student creation on first scan
- **Problem**: Students may check in without pre-registration
- **Solution**: Upsert pattern - create student record if not exists based on composite unique key
- **Deduplication**: Unique constraints prevent duplicate student records and same-day check-ins

### API Structure

**Endpoints**:
- Student management: Create students via form submission
- QR generation: Bulk generate QR codes for all students
- Check-in: POST endpoint accepting scanned QR text
- Live view: GET endpoint returning grouped attendance data
- Static file serving: Serves HTML pages and JavaScript libraries

## External Dependencies

### Python Libraries
- **FastAPI**: Web framework for API endpoints
- **SQLAlchemy**: ORM for database operations
- **qrcode**: QR code image generation
- **Pydantic**: Request/response validation via BaseModel

### JavaScript Libraries
- **jsQR**: Client-side QR code decoder (vendored in static/js/)

### Browser APIs
- **getUserMedia**: Camera access for QR scanning
- **Canvas API**: Image processing for QR detection

### Database
- **SQLite**: Embedded database (no external service)
- **Connection**: File-based (attendance.db in application directory)