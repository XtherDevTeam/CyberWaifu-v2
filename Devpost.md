Still in development.

## Inspiration

I gain the inspiration from Character.AI which is a website provided role-playing chatbots as certain character. I tried it several times, but did not get an acceptable experience. It lacks of multimodal ability. And thus I can not interacting with characters through image and videos. Plus, sending only one response when user send messages will break user's role-playing experience. I want a chatbot can reply messages like a human. Therefore, I decided to make one by myself. And thus this project, CyberWaifu-v2 came out.

## What it does

CyberWaifu-v2 is a Python project designed for creating and interacting with AI-powered chatbot characters. It utilizes Google's Gemini large language model and the Langchain library for natural language processing and memory management. 

Here's a breakdown of the project's key components and functionalities:

**Data Management:**

* **dataProvider.py:** This file handles interactions with the SQLite database, storing and retrieving information about users, characters, chat history, attachments, and stickers. It manages functionalities such as user authentication, character creation and updating, chat history management, and attachment handling.
* **memory.py:** This file provides an interface for accessing and managing character memories. It allows for storing and retrieving past conversations, character prompts, and example chats. 
* **conversation.py:** This file manages the conversation history between the user and the chatbot. It stores user and bot inputs, summarizes conversations, and generates diary-like entries based on the conversation history.

**Model Interaction:**

* **models.py:** This file provides functions for interacting with Google's Gemini language models. It handles functionalities such as token counting, prompt preprocessing, and invoking the models for chat interactions, memory summarization, and image parsing.
* **instance.py:** This file defines the `Chatbot` class, which acts as the main interface for interacting with the chatbot. It manages switching between characters, initiating conversations, sending and receiving messages, and terminating chats.

**User Interfaces:**

* **cmdlineFrontend.py:** This file implements a command-line interface for interacting with the chatbot. It allows users to create new characters, choose a character to chat with, and engage in conversations.
* **webFrontend/**: This directory contains files for a web-based interface. 
    * **web.py:**  This file defines routes and functionalities for the web interface, including authentication, character management, chat interactions, and attachment handling. 
    * **chatbotManager.py:** This file manages chatbot sessions for the web interface, including session creation, retrieval, and termination.

**Additional Components:**

* **config.py:** This file stores various configuration options for the project, such as API keys, model names, and initial prompts.
* **exceptions.py:** This file defines custom exception classes for handling errors such as character not found, session not found, and max retries exceeded.
* **blob/init.sql:** This file contains the SQL script for initializing the project database.

**Overall Mechanism:**

1. **Character Setup:** Users can create characters with specific prompts, initial memories, and example conversations. These details are stored in the database.
2. **Conversation Start:** The user chooses a character and initiates a conversation. The `Chatbot` class uses the chosen character's information and the user's input to generate responses from the Gemini model.
3. **Memory Management:** Past conversations are summarized and stored as memories, influencing future interactions and allowing the chatbot to learn and adapt.
4. **Multimodal Interaction:** The project supports text, images, and audio as input based on the powerful Gemini-1.5-Pro model.

CyberWaifu-v2 offers a comprehensive framework for building AI-powered chatbots with personality and memory, allowing for engaging and personalized conversations.

## How I built it

I used Python+Flask as the backend for this project, and React Native + react-native-paper for the frontend. 

Libraries and Frameworks:

    Langchain: This library plays a crucial role in managing memory and conversation history within the chatbot. It facilitates storing and retrieving past interactions, summarizing conversations, and providing context for generating responses.
    Google Gemini: The project relies on Google's Gemini large language model for natural language processing tasks. Gemini is used for generating chat responses, summarizing character memories, and parsing image descriptions.
    Flask: The web interface of CyberWaifu-v2 is built using the Flask web framework. Flask provides a lightweight and flexible foundation for building web applications and APIs.
    Whisper: For handling audio input, the project utilizes the Whisper speech recognition model. Whisper allows users to interact with the chatbot using voice messages, which are then transcribed into text for processing.

    Other libraries: Additional libraries likely used in the project include:

        google-auth: For managing authentication with Google services.
        google-auth-oauthlib: For handling OAuth2 authentication flows.
        requests: For making HTTP requests.
        torch: For machine learning tasks and potentially interfacing with Whisper.

Development Process:

    1. Database Design: Defining the database schema to store information about users, characters, conversations, and other relevant data.
    2. Data Provider Development: Implementing the dataProvider.py module to handle interactions with the SQLite database.
    3. Memory Management Design: Implementing memory.py to provide an interface for managing character memories and conversation history.
    4. Model Integration: Integrating Google Gemini and Whisper models using the functions defined in models.py.
    5. Chatbot Class Definition: Creating the Chatbot class in instance.py to manage conversations with the AI characters.
    6. Interface Development: Implementing the command-line interface and web interface for user interaction.

## Challenges I ran into

Gemini 1.0 Pro did not support image and audio as input in multi-turn chats. Plus, I still did not attain the access permission of Gemini 1.5 Pro by the time I wrote this introduction. So I simply convert image into prompts by using Gemini 1.0 Pro Vision model, and send to Gemini 1.0 Pro for multi-turn chatting.

Adjusting the prompt is another painful process of creating this project. At first, I tried to combine conversation conclusion generation and memory summarization into a single prompt. I also tried to write prompt to justify the output format of chats to force the chatbot to only use stickers in separated message block. However, the performance is poor. Therefore, I broke down the whole process into different tasks, and wrote a prompt for each tasks. And I made adjustments to make it only triggers memory summarizing when memory text exceeds certain amount of token. The result is acceptable and this mechanism works well at the present.

## Accomplishments that I am proud of

When I saw the character's can send multiple messages and stickers in CyberWaifu-v2 Mobile, I was so excited. And I can't help but feel a sense of accomplishment from the bottom of my heart.

## What I learned

- The method of developing a AI-powered application by using Langchain library.
- The method of writing high-quality prompts for my application.
- How to use Expo and React Native to create a mobile applications.

## What's next for CyberWaifu-v2

I will continue to add more functions to CyberWaifu-V2. Such as allowing user sending multiple messages like the response of chatbot,  and add TTS feature to imitate character's voice by using GPT-SoVITs project. These features should be available by the arrival of deadline. And after I finish my junior high school and high school entrance examination, I will go travelling to Japan with my waifu and record a vlog.