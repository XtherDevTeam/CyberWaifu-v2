# CyberWaifu Web Service API Documentation

## Base URL

The base URL for all endpoints is `/api/v1`.

## Endpoints

### 1. **Service Information**
- **Endpoint**: `/service/info`
- **Method**: GET
- **Description**: Retrieves information about the CyberWaifu Web Service API.
- **Response**: 
    - `data`: Information about the service including initialization status, API version, name, image model usage, chat model usage, authenticated session status, and session username.
    - `status`: Indicates the success or failure of the request.

### 2. **User Login**
- **Endpoint**: `/user/login`
- **Method**: POST
- **Description**: Logs in a user to the Yoimiya service.
- **Request Body**:
    - `password`: Password of the user.
- **Response**: 
    - `data`: Message indicating success or failure.
    - `status`: Indicates the success or failure of the request.

### 3. **Character List**
- **Endpoint**: `/char_list`
- **Method**: POST
- **Description**: Retrieves the list of characters.
- **Response**: 
    - `data`: List of characters.
    - `status`: Indicates the success or failure of the request.

### 4. **Establish Chat**
- **Endpoint**: `/chat/establish`
- **Method**: POST
- **Description**: Establishes a chat session with a character.
- **Request Body**:
    - `charName`: Name of the character.
    - `msgChain`: Message chain to begin the chat.
- **Response**: 
    - `response`: Response from the chatbot.
    - `session`: Session ID.
    - `status`: Indicates the success or failure of the request.

### 5. **Send Chat Message**
- **Endpoint**: `/chat/message`
- **Method**: POST
- **Description**: Sends a message in an active chat session.
- **Request Body**:
    - `session`: Session ID.
    - `msgChain`: Message chain.
- **Response**: 
    - `response`: Response from the chatbot.
    - `session`: Session ID.
    - `status`: Indicates the success or failure of the request.

### 6. **Terminate Chat**
- **Endpoint**: `/chat/terminate`
- **Method**: POST
- **Description**: Terminates an active chat session.
- **Request Body**:
    - `session`: Session ID.
- **Response**: 
    - `data`: Message indicating success.
    - `status`: Indicates the success or failure of the request.

### 7. **Upload Audio Attachment**
- **Endpoint**: `/attachment/upload/audio`
- **Method**: POST
- **Description**: Uploads an audio attachment.
- **Response**: 
    - `data`: Message indicating success.
    - `id`: ID of the uploaded attachment.
    - `status`: Indicates the success or failure of the request.

### 8. **Upload Image Attachment**
- **Endpoint**: `/attachment/upload/image`
- **Method**: POST
- **Description**: Uploads an image attachment.
- **Response**: 
    - `data`: Message indicating success.
    - `id`: ID of the uploaded attachment.
    - `status`: Indicates the success or failure of the request.

### 9. **Download Attachment**
- **Endpoint**: `/attachment/<attachmentId>`
- **Method**: GET
- **Description**: Downloads an attachment by ID.
- **Response**: File data.

### 10. **Character Avatar**
- **Endpoint**: `/char/<id>/avatar`
- **Method**: GET
- **Description**: Retrieves the avatar of a character by ID.
- **Response**: File data.

### 11. **Create New Character**
- **Endpoint**: `/char/new`
- **Method**: POST
- **Description**: Creates a new character.
- **Request Body**:
    - `charName`: Name of the character.
    - `charPrompt`: Character prompt.
    - `pastMemories`: Past memories of the character.
    - `exampleChats`: Example chats for the character.
- **Response**: 
    - `data`: Message indicating success.
    - `status`: Indicates the success or failure of the request.

### 12. **Fetch Character Chat History**
- **Endpoint**: `/char/<id>/history/<offset>`
- **Method**: POST
- **Description**: Fetches the chat history of a character.
- **Response**: 
    - `data`: Chat history.
    - `status`: Indicates the success or failure of the request.

### 13. **Get Avatar**
- **Endpoint**: `/avatar`
- **Method**: POST
- **Description**: Retrieves the avatar.
- **Response**: File data.

### 14. **Create Sticker Set**
- **Endpoint**: `/sticker/create_set`
- **Method**: POST
- **Description**: Creates a new sticker set.
- **Request Body**:
    - `setName`: Name of the sticker set.
- **Response**: 
    - `status`: Indicates the success or failure of the request.

### 15. **Delete Sticker Set**
- **Endpoint**: `/sticker/delete_set`
- **Method**: POST
- **Description**: Deletes a sticker set.
- **Request Body**:
    - `setId`: ID of the sticker set.
- **Response**: 
    - `status`: Indicates the success or failure of the request.

### 16. **Add Sticker to Set**
- **Endpoint**: `/sticker/add`
- **Method**: POST
- **Description**: Adds a sticker to a set.
- **Query Parameters**:
    - `setId`: ID of the sticker set.
    - `stickerName`: Name of the sticker.
- **Response**: 
    - `status`: Indicates the success or failure of the request.

### 17. **Delete Sticker**
- **Endpoint**: `/sticker/delete`
- **Method**: POST
- **Description**: Deletes a sticker.
- **Request Body**:
    - `stickerId`: ID of the sticker.
- **Response**: 
    - `status`: Indicates the success or failure of the request.

### 18. **Get Sticker**
- **Endpoint**: `/sticker/get`
- **Method**: GET
- **Description**: Retrieves a sticker.
- **Query Parameters**:
    - `setId`: ID of the sticker set.
    - `name`: Name of the sticker.
- **Response**: File data.

### 19. **List Stickers**
- **Endpoint**: `/sticker/list`
- **Method**: POST
- **Description**: Retrieves a list of stickers.
- **Response**: 
    - `data`: List of stickers.
    - `status`: Indicates the success or failure of the request.

### 20. **Initialize**
- **Endpoint**: `/initialize`
- **Method**: POST
- **Description**: Initializes the Yoimiya service.
- **Request Body**:
    - `userName`: Username for initialization.
    - `password`: Password for initialization.
- **Response**: 
    - `data`: Message indicating success.
    - `status`: Indicates the success or failure of the request.