## CyberWaifu API Documentation

### Overview

This document details the API endpoints for the Yoimiya application, which appears to be a chatbot application with character management and multimedia functionalities. The API utilizes JSON for data exchange and requires authentication for most actions.

### Categories

-   **Service Information:** Provides information about the Yoimiya service. 
-   **User Management:** Handles user authentication and sessions.
-   **Character Management:** Allows creation, editing, and information retrieval for chatbot characters. 
-   **Chat Management:**  Facilitates the establishment, interaction, and termination of chat sessions with characters.
-   **Attachment Management:** Enables uploading and downloading of audio and image attachments. 
-   **Sticker Management:** Provides functionalities for creating, deleting, and managing sticker sets and individual stickers.
-   **Speech-to-Text:** Converts audio input to text.
-   **Avatar Management:** Allows updating of user and character avatars.
-   **Initialization:** Initializes the CyberWaifu service.

### Endpoints

#### Service Information

##### **URL:** /api/v1/service/info
-   **Method:** GET
-   **Description:** Retrieves information about the CyberWaifu service, including API version, initialization status, supported features, and user authentication status.
-   **Request Form:** N/A
-   **Response Description:** JSON object containing service information.
-   **Response Example:**

```json
{
  "data": {
    "initialized": true,
    "api_ver": "v1",
    "api_name": "Yoimiya",
    "image_model": "gemini-pro-vision",
    "chat_model": "gemini-pro",
    "authenticated_session": 1668776400,
    "session_username": "ExampleUser"
  },
  "status": true
}
```

#### User Management

##### **URL:** /api/v1/user/login
-   **Method:** POST
-   **Description:** Authenticates a user with the provided password.
-   **Request Form:** JSON object with a "password" field.
-   **Request Example:**

```json
{
  "password": "example_password"
}
```

-   **Response Description:** JSON object indicating success or failure, with an optional message.
-   **Response Example (Success):** 

```json
{
  "data": "success",
  "status": true
}
```

-   **Response Example (Failure):** 

```json
{
  "data": "invalid password",
  "status": false
}
``` 

#### Character Management

##### **URL:** /api/v1/char_list
-   **Method:** POST
-   **Description:** Retrieves a list of available characters.
-   **Request Form:** N/A
-   **Response Description:** JSON object containing a list of character information.
-   **Response Example:**

```json
{
  "data": [
    {
      "id": 1,
      "name": "Character A",
      "useStickerSet": 1
    },
    {
      "id": 2,
      "name": "Character B",
      "useStickerSet": 0 
    }
  ],
  "status": true
} 
```

##### **URL:** /api/v1/char/{id}/info
-   **Method:** POST
-   **Description:** Retrieves detailed information about a specific character.
-   **Request Form:** N/A
-   **Response Description:** JSON object containing character details such as name, prompt, memories, and example chats. 
-   **Response Example:** 

```json
{
  "data": {
    "id": 1,
    "name": "Character A",
    "useStickerSet": 1,
    "prompt": "A cheerful and helpful character.",
    "memories": "Character A has a strong sense of justice...",
    "exampleChats": "User: Hi there!\nCharacter A: Hello! How can I assist you today?" 
  },
  "status": true
}
```

##### **URL:** /api/v1/char/{id}/avatar
-   **Method:** GET
-   **Description:** Downloads the avatar image of a specific character. 
-   **Request Form:** N/A
-   **Response Description:** Image file (e.g., PNG, JPEG) 
##### **URL:** /api/v1/char/{id}/edit 
-   **Method:** POST
-   **Description:** Updates the information of a specific character.
-   **Request Form:** JSON object containing fields for character name, prompt, memories, example chats, and sticker set usage. 
-   **Request Example:** 

```json 
{
  "charName": "Updated Character A",
  "charPrompt": "An even more cheerful and helpful character.",
  "pastMemories": "Updated memories...",
  "exampleChats": "Updated example chat...", 
  "useStickerSet": 1
}
```

-   **Response Description:** JSON object indicating success or failure. 
-   **Response Example:** 

```json
{
  "data": "success",
  "status": true
} 
```

##### **URL:** /api/v1/char/new 
-   **Method:** POST
-   **Description:** Creates a new character. 
-   **Request Form:** JSON object containing fields for character name, prompt, memories, and example chats. 
-   **Request Example:**

```json
{
  "charName": "New Character",
  "charPrompt": "A brand new character.",
  "pastMemories": "Initial memories...",
  "exampleChats": "Initial example chat..." 
}
```

-   **Response Description:** JSON object indicating success or failure. 
-   **Response Example:** 

```json
{
  "data": "success",
  "status": true
} 
```

##### **URL:** /api/v1/char/{id}/history/{offset}
-   **Method:** POST 
-   **Description:** Retrieves chat history for a specific character with an optional offset. 
-   **Request Form:** N/A 
-   **Response Description:** JSON object containing chat history entries. 
-   **Response Example:**

```json 
{
  "data": [
    {
      "timestamp": 1668776400,
      "message": "User: Hello!",
      "sender": "user" 
    },
    {
      "timestamp": 1668776405,
      "message": "Character A: Hi there!",
      "sender": "character" 
    }
  ],
  "status": true
} 
```

##### **URL:** /api/v1/char/{id}/avatar/update
-   **Method:** POST 
-   **Description:** Updates the avatar image of a specific character. 
-   **Request Form:** Form data with an image file. 
-   **Response Description:** JSON object indicating success or failure. 
-   **Response Example:** 

```json
{
  "status": true 
}
```



#### Chat Management

##### **URL:** /api/v1/chat/establish 
-   **Method:** POST
-   **Description:** Initiates a new chat session with a specific character. 
-   **Request Form:** JSON object containing the character name and an initial message chain.
-   **Request Example:**

```json 
{
  "charName": "Character A",
  "msgChain": ["Hello!"]
} 
```

-   **Response Description:** JSON object containing the session ID, initial response from the character, and status. 
-   **Response Example:**

```json 
{ 
  "response": ["Character A: Hi there!"], 
  "session": "session_id",
  "status": true
}
``` 

##### **URL:** /api/v1/chat/message 
-   **Method:** POST 
-   **Description:** Sends a message to a specific chat session and receives a response. 
-   **Request Form:** JSON object containing the session ID and a message chain.
-   **Request Example:**

```json 
{ 
  "session": "session_id",
  "msgChain": ["How are you?"]
} 
``` 

-   **Response Description:** JSON object containing the response from the character, session ID, and status. 
-   **Response Example:** 

```json
{
  "response": ["Character A: I'm doing well, thank you!"],
  "session": "session_id",
  "status": true
}
``` 

##### **URL:** /api/v1/chat/terminate
-   **Method:** POST 
-   **Description:** Ends a specific chat session.
-   **Request Form:** JSON object containing the session ID.
-   **Request Example:**

```json 
{ 
  "session": "session_id" 
} 
``` 

-   **Response Description:** JSON object indicating success or failure. 
-   **Response Example:**

```json 
{
  "data": "success",
  "status": true 
} 
```

#### Attachment Management 

##### **URL:** /api/v1/attachment/upload/audio
-   **Method:** POST 
-   **Description:** Uploads an audio file as an attachment. 
-   **Request Form:** Form data with an audio file (e.g., MP3, WAV). 
-   **Response Description:** JSON object indicating success or failure, with an ID for the uploaded attachment. 
-   **Response Example:**

```json
{
  "data": "success",
  "id": "attachment_id",
  "status": true
} 
```

##### **URL:** /api/v1/attachment/upload/image
-   **Method:** POST
-   **Description:** Uploads an image file as an attachment.
-   **Request Form:** Form data with an image file (e.g., PNG, JPEG).
-   **Response Description:** JSON object indicating success or failure, with an ID for the uploaded attachment.
-   **Response Example:** 

```json
{
  "data": "success",
  "id": "attachment_id", 
  "status": true
} 
```

##### **URL:** /api/v1/attachment/{attachmentId} 
-   **Method:** GET 
-   **Description:** Downloads a specific attachment. 
-   **Request Form:** N/A 
-   **Response Description:** The requested attachment file (audio or image). 

#### Sticker Management 

##### **URL:** /api/v1/sticker/create_set 
-   **Method:** POST 
-   **Description:** Creates a new sticker set. 
-   **Request Form:** JSON object with a "setName" field. 
-   **Request Example:** 

```json
{
  "setName": "My Sticker Set" 
}
```

-   **Response Description:** JSON object indicating success or failure.
-   **Response Example:** 

```json 
{ 
  "status": true 
} 
```

##### **URL:** /api/v1/sticker/delete_set
-   **Method:** POST 
-   **Description:** Deletes a sticker set.
-   **Request Form:** JSON object with a "setId" field.
-   **Request Example:** 

```json
{
  "setId": 1 
} 
```

-   **Response Description:** JSON object indicating success or failure. 
-   **Response Example:** 

```json
{ 
  "status": true
}
``` 

##### **URL:** /api/v1/sticker/add 
-   **Method:** POST 
-   **Description:** Adds a new sticker to a sticker set.
-   **Request Form:** Form data with "setId" and "stickerName" parameters, and an image file for the sticker.
-   **Response Description:** JSON object indicating success or failure. 
-   **Response Example:**

```json 
{ 
  "status": true 
} 
``` 

##### **URL:** /api/v1/sticker/delete
-   **Method:** POST
-   **Description:** Deletes a sticker from a sticker set. 
-   **Request Form:** JSON object with a "stickerId" field.
-   **Request Example:** 

```json 
{
  "stickerId": 1 
} 
``` 

-   **Response Description:** JSON object indicating success or failure. 
-   **Response Example:**

```json
{
  "status": true 
}
``` 

##### **URL:** /api/v1/sticker/get 
-   **Method:** GET 
-   **Description:** Retrieves a specific sticker from a sticker set.
-   **Request Form:** Query parameters with "setId" and "name" fields. 
-   **Response Description:** The requested sticker image file. 

##### **URL:** /api/v1/sticker/set_info
-   **Method:** POST
-   **Description:** Retrieves information about a sticker set. 
-   **Request Form:** JSON object with a "setId" field. 
-   **Request Example:** 

```json 
{
  "setId": 1 
}
``` 

-   **Response Description:** JSON object containing sticker set information, including name and sticker list.
-   **Response Example:**

```json
{
  "data": {
    "id": 1,
    "name": "My Sticker Set", 
    "stickers": [
      {
        "id": 1, 
        "name": "Sticker 1" 
      },
      {
        "id": 2, 
        "name": "Sticker 2" 
      }
    ]
  }, 
  "status": true
} 
```

##### **URL:** /api/v1/sticker/rename_set 
-   **Method:** POST 
-   **Description:** Renames a sticker set.
-   **Request Form:** JSON object with "setId" and "newSetName" fields. 
-   **Request Example:**

```json 
{ 
  "setId": 1,
  "newSetName": "My Updated Sticker Set" 
} 
```

-   **Response Description:** JSON object indicating success or failure.
-   **Response Example:** 

```json 
{ 
  "status": true 
} 
```

##### **URL:** /api/v1/sticker/set_list
-   **Method:** POST
-   **Description:** Retrieves a list of available sticker sets. 
-   **Request Form:** N/A 
-   **Response Description:** JSON object containing a list of sticker set information (id and name). 
-   **Response Example:** 

```json 
{ 
  "data": [
    {
      "id": 1, 
      "name": "My Sticker Set"
    },
    {
      "id": 2, 
      "name": "Another Sticker Set"
    }
  ], 
  "status": true
} 
```

##### **URL:** /api/v1/sticker/list 
-   **Method:** POST
-   **Description:** Retrieves a list of stickers within a specific sticker set.
-   **Request Form:** JSON object with a "setId" field.
-   **Request Example:** 

```json 
{
  "setId": 1 
} 
```

-   **Response Description:** JSON object containing a list of sticker information (id and name) within the specified set. 
-   **Response Example:**

```json 
{
  "data": [ 
    {
      "id": 1, 
      "name": "Sticker 1" 
    },
    {
      "id": 2, 
      "name": "Sticker 2"
    } 
  ],
  "status": true
}
``` 

#### Speech-to-Text 

##### **URL:** /api/v1/stt
-   **Method:** POST
-   **Description:** Converts an audio file to text. 
-   **Request Form:** Form data with an audio file (e.g., MP3, WAV). 
-   **Response Description:** JSON object containing the recognized text and status.
-   **Response Example:**

```json
{ 
  "status": true, 
  "data": "This is the recognized text." 
} 
```

#### Avatar Management

##### **URL:** /api/v1/avatar
-   **Method:** GET
-   **Description:** Retrieves the user's avatar image.
-   **Request Form:** N/A
-   **Response Description:** The user's avatar image file.
##### **URL:** /api/v1/avatar/update
-   **Method:** POST 
-   **Description:** Updates the user's avatar image.
-   **Request Form:** Form data with an image file. 
-   **Response Description:** JSON object indicating success or failure.
-   **Response Example:**

```json 
{
  "status": true
}
``` 

#### Initialization 

##### **URL:** /api/v1/initialize
-   **Method:** POST 
-   **Description:** Initializes the Yoimiya service with a username and password. 
-   **Request Form:** JSON object with "userName" and "password" fields.
-   **Request Example:**

```json
{
  "userName": "NewUser",
  "password": "new_password" 
}
```

-   **Response Description:** JSON object indicating success or failure, with an optional message. 
-   **Response Example:**

```json 
{ 
  "data": "success",
  "status": true
}
``` 