# API Documentation for Web Service

## Authentication

### `POST /api/v1/user/login`

- **Description:** User login to authenticate the session.

- **Parameters:**

  - `password` (string): User password.

- **Response:**

  - Success: `{ "data": "success", "status": true }`

  - Failure: `{ "data": "invalid form", "status": false }` or `{ "data": "invalid password", "status": false }`

## Character List

### `POST /api/v1/char_list`

- **Description:** Get the list of characters.

- **Authentication:** Requires an authenticated session.

- **Response:**

  - Success: `{ "data": [character_list], "status": true }`

  - Failure: `{ "data": "not authenticated", "status": false }` or `{ "data": "not initialized", "status": false }`

## Chat Establishment

### `POST /api/v1/chat/establish`

- **Description:** Establish a chat session with a character.

- **Parameters:**

  - `charName` (string): Character name.

  - `msgChain` (string): Initial message chain.

- **Authentication:** Requires an authenticated session.

- **Response:**

  - Success: `{ "response": "chat_response", "session": "session_id", "status": true }`

  - Failure: `{ "data": "not authenticated", "status": false }` or `{ "data": "not initialized", "status": false }` or `{ "data": "invalid form", "status": false }`

## Send Chat Message

### `POST /api/v1/chat/message`

- **Description:** Send a message in an existing chat session.

- **Parameters:**

  - `session` (string): Chat session ID.

  - `msgChain` (string): Message chain.

- **Authentication:** Requires an authenticated session.

- **Response:**

  - Success: `{ "response": "chat_response", "session": "session_id", "status": true }`

  - Failure: `{ "data": "not authenticated", "status": false }` or `{ "data": "not initialized", "status": false }` or `{ "data": "invalid form", "status": false }`

## Terminate Chat Session

### `POST /api/v1/chat/terminate`

- **Description:** Terminate an existing chat session.

- **Parameters:**

  - `session` (string): Chat session ID.

- **Authentication:** Requires an authenticated session.

- **Response:**

  - Success: `{ "data": "success", "status": true }`

  - Failure: `{ "data": "not authenticated", "status": false }` or `{ "data": "not initialized", "status": false }` or `{ "data": "invalid form", "status": false }`

## Attachment Upload - Audio

### `POST /api/v1/attachment/upload/audio`

- **Description:** Upload an audio attachment.

- **Authentication:** Requires an authenticated session.

- **Response:**

  - Success: `{ "data": "success", "id": "attachment_id", "status": true }`

  - Failure: `{ "data": "not authenticated", "status": false }` or `{ "data": "not initialized", "status": false }` or `{ "data": "invalid mimetype expect 'audio/'", "status": false }`

## Attachment Upload - Image

### `POST /api/v1/attachment/upload/image`

- **Description:** Upload an image attachment.

- **Authentication:** Requires an authenticated session.

- **Response:**

  - Success: `{ "data": "success", "id": "attachment_id", "status": true }`

  - Failure: `{ "data": "not authenticated", "status": false }` or `{ "data": "not initialized", "status": false }` or `{ "data": "invalid mimetype expect 'image/'", "status": false }`

## Attachment Download

### `POST /api/v1/attachment/<attachmentId>`

- **Description:** Download an attachment.

- **Parameters:**

  - `attachmentId` (string): Attachment ID.

- **Authentication:** Requires an authenticated session.

- **Response:**

  - Success: Returns the file.

  - Failure: `{ "data": "not authenticated", "status": false }` or `{ "data": "not initialized", "status": false }`