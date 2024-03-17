# CyberWaifu Web Service API Documentation

## Overview

The CyberWaifu Web Service provides an API for interacting with the CyberWaifu application. This documentation outlines the available endpoints, request formats, and response formats for the API.

**Base URL:** `/api/v1`

## Authentication

The API uses session-based authentication. Clients must include a valid session token in the request headers to access protected endpoints.

## Endpoints

### 1. Service Information

#### `GET /service/info`

**Description:** Retrieve information about the CyberWaifu service.

**Request:**
```http
GET /api/v1/service/info
```

**Response:**
```json
{
	"data": {
		"initialized": true,
		"api_ver": "v1",
		"api_name": "yoimiya",
		"image_model": "gemini-pro-vision",
		"chat_model": "gemini-pro-latest",
		"authenticated_session": 1614755532
	},
	"status": true
}
```

### 2. User Login

#### `POST /user/login`

**Description:** Authenticate a user and establish a session.

**Request:**
```http
POST /api/v1/user/login
```

**Request Body:**
```json
{
"password": "user_password"
}
```

**Response:**
```json
{
"data": "success",
"status": true
}
```

### 3. Character List

#### `POST /char_list`

**Description:** Get the list of characters.

**Request:**
```http
POST /api/v1/char_list
```

**Response:**
```json
{
"data": ["character1", "character2"],
"status": true
}
```

### 4. Chat Establishment

#### `POST /chat/establish`

**Description:** Start a chat session with a specified character.

**Request:**
```http
POST /api/v1/chat/establish
```

**Request Body:**
```json
{
"charName": "character_name",
"msgChain": ["message1", "message2"]
}
```

**Response:**
```json
{
"response": "chat_response",
"session": "session_token",
"status": true
}
```

### 5. Chat Message

#### `POST /chat/message`

**Description:** Send a message in an existing chat session.

**Request:**
```http
POST /api/v1/chat/message
```

**Request Body:**
```json
{
"session": "session_token",
"msgChain": ["message3", "message4"]
}
```

**Response:**
```json
{
"response": "chat_response",
"session": "session_token",
"status": true
}
```

### 6. Chat Termination

#### `POST /chat/terminate`

**Description:** Terminate an existing chat session.

**Request:**
```http
POST /api/v1/chat/terminate
```

**Request Body:**
```json
{
"session": "session_token"
}
```

**Response:**
```json
{
"data": "success",
"status": true
}
```

### 7. Audio Attachment Upload

#### `POST /attachment/upload/audio`

**Description:** Upload an audio attachment.

**Request:**

```http
POST /api/v1/attachment/upload/audio
```

**Request Body (Multipart Form Data):**
- `audio_file`: (audio file)
  

**Response:**
```json
{
"data": "success",
"id": "attachment_id",
"status": true
}
```

### 8. Image Attachment Upload

#### `POST /attachment/upload/image`

**Description:** Upload an image attachment.

**Request:**
```http
POST /api/v1/attachment/upload/image
```

**Request Body (Multipart Form Data):**
- `image_file`: (image file)
  

**Response:**
```json
{
"data": "success",
"id": "attachment_id",
"status": true
}
```

### 9. Attachment Download

#### `POST /attachment/<attachmentId>`

**Description:** Download an attachment by ID.

**Request:**
```http
POST /api/v1/attachment/attachment_id
```

**Response:**
Attachment file

### 10. Initialization

#### `POST /initialize`

**Description:** Initialize the CyberWaifu service.

**Request:**
```http
POST /api/v1/initialize
```

**Request Body:**
```json
{
"userName": "admin_user",
"password": "admin_password"
}
```

**Response:**
```json
{
"data": "success",
"status": true
}
```

## Running the Service

To start the CyberWaifu service, invoke the `invoke` function provided in the code. The service runs on the specified host and port as configured in `webFrontend.config`.

```python
invoke()
```