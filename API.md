## API Documentation

### Authentication

#### User Login
- **URL**: `/api/v1/user/login`
- **Method**: POST
- **Description**: Authenticate user login and start a session.
- **Request Format**:
  ```json
  {
    "password": "user_password"
  }
  ```
- **Response Format**:
  ```json
  {
    "data": "success",
    "status": true
  }
  ```
  or
  ```json
  {
    "data": "invalid password",
    "status": false
  }
  ```

### Chat Operations

#### Character List
- **URL**: `/api/v1/char_list`
- **Method**: POST
- **Description**: Retrieve a list of characters.
- **Request Format**: None
- **Response Format**:
  ```json
  {
    "data": ...,
    "status": true
  }
  ```

#### Establish Chat
- **URL**: `/api/v1/chat/establish`
- **Method**: POST
- **Description**: Begin a chat session with a selected character.
- **Request Format**:
  ```json
  {
    "charName": "character_name",
    "beginMsg": "initial_message"
  }
  ```
- **Response Format**:
  ```json
  {
    "response": "chatbot_response",
    "session": "session_id",
    "status": true
  }
  ```

#### Send Chat Message
- **URL**: `/api/v1/chat/message`
- **Method**: POST
- **Description**: Send a message in an existing chat session.
- **Request Format**:
  ```json
  {
    "session": "session_id",
    "msgChain": ["message1", "message2", ...]
  }
  ```
- **Response Format**:
  ```json
  {
    "response": "chatbot_response",
    "session": "session_id",
    "status": true
  }
  ```

#### Terminate Chat
- **URL**: `/api/v1/chat/terminate`
- **Method**: POST
- **Description**: End an ongoing chat session.
- **Request Format**:
  ```json
  {
    "session": "session_id"
  }
  ```
- **Response Format**:
  ```json
  {
    "data": "success",
    "status": true
  }
  ```

### File Attachments

#### Upload Audio Attachment
- **URL**: `/api/v1/attachment/upload/audio`
- **Method**: POST
- **Description**: Upload an audio attachment to the chat session.
- **Request Format**: FormData with audio file
- **Response Format**:
  ```json
  {
    "data": "success",
    "status": true
  }
  ```

### Notes
- All endpoints require authentication. If not authenticated or session expired, appropriate error responses will be returned.
- Responses include a `status` field indicating the success or failure of the request.