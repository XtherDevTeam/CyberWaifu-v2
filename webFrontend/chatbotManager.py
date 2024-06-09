import asyncio
from os import remove
import os
import queue
import re
import threading
from typing import Optional

import av
from cv2 import broadcast
import cv2
import livekit.api
import livekit.rtc
from mirai import Voice
from numpy import char
import numpy
from pyparsing import Opt
import requests
from sympy import rem
from GPTSoVits import GPTSoVitsAPI
import dataProvider
import memory
import uuid
import time
import instance
import exceptions
import random
import livekit
import google.ai.generativelanguage as glm
import webFrontend.config
import webrtcvad
import google.generativeai
import chatModel

from models import EmojiToStickerInstrctionModel, TokenCounter

import emoji


def removeEmojis(text):
    return emoji.replace_emoji(text, '')


class VoiceChatSession:
    """
    Real time chat session for a character.


    Attributes:
        sessionName (str): session name
        charName (str): character name
        bot (instance.Chatbot): chatbot object for the real time session
        chatRoom (Optional[livekit.rtc.Room]): livekit room object for the real time session
        dataProvider (dataProvider.DataProvider): data provider object
        currentImageFrame (Optional[livekit.rtc.VideoFrame]): current image frame from the user's camera or sharing screen
        broadcastAudioTrack (Optional[livekit.rtc.AudioTrack]): audio track for broadcasting audio to other users in the session

    Methods:
        VAD(stream: livekit.rtc.AudioStream) -> None: Voice activity detection.
        receiveVideoStream(stream: livekit.rtc.VideoStream) -> None: Receive video stream from other user.
        start(botToken: str) -> None: Start the hoster of chat session.
        chatPluginGetUserMedia() -> glm.File: Get image of user's camera or sharing screen. Use it when user want you to know about the content of his camera or screen or your response is related to the content of the camera or screen.
    """

    def __init__(self, sessionName: str, charName: str, dataProvider: dataProvider.DataProvider) -> None:
        self.sessionName = sessionName
        self.charName = charName
        self.bot = instance.Chatbot(memory.Memory(
            dataProvider, charName), dataProvider.getUserName(), [self.chatPluginGetUserMedia])
        self.chatRoom: Optional[livekit.rtc.Room] = None
        self.dataProvider = dataProvider
        self.currentImageFrame: Optional[livekit.rtc.VideoFrame] = None
        self.broadcastAudioTrack: Optional[livekit.rtc.AudioTrack] = None
        self.broadcastMissions: queue.Queue[dict[str, str | int | bool]] = []
        self.currentBroadcastMission: Optional[av.InputContainer |
                                               av.OutputContainer] = None
        self.ttsServiceId = self.bot.memory.getCharTTSServiceId()
        self.ttsService = self.dataProvider.getGPTSoVitsService(
            self.ttsServiceId)
        self.GPTSoVITsAPI = GPTSoVitsAPI(self.ttsService['url'])
        self.vadModel = webrtcvad.Vad(3)

    async def chat(self, audios: list[glm.File]) -> None:
        """
        Send audio files to chatbot and retrive response as broadcast missions.

        Args:
            audios (list[glm.File]): list of audio files

        Returns:
            None
        """

        resp = []
        # no to use self.bot.chat here cuz we've already uploaded the files.
        if self.bot.inChatting:
            resp = self.bot.llm.chat(audios)
        else:
            resp = self.bot.llm.initiate(audios)
            self.bot.inChatting = True
        for i in self.dataProvider.parseModelResponse(resp):
            self.broadcastMissions.put(i)

    async def VAD(self, stream: livekit.rtc.AudioStream) -> None:
        """
        Voice activity detection.
        Fetch and identify each audio frame, when activity detected, save to local temporary file and upload as glm.File then send to Gemini model as Input.

        Args:
            stream (livekit.rtc.AudioStream): audio stream

        Returns:
            None
        """
        # a simple implemenation of WebRTC VAD algorithm
        ring_buffer: list[tuple[bytes, bool]] = []
        voiced_frames: list[bytes] = []
        bs = []
        # i don't even know whether it's a good idea to use 648 as the maxlen.
        maxlen = 30
        triggered = False
        async for frame in stream:
            byteFrame = frame.frame.data.tobytes()
            isSpeech = self.vadModel.is_speech(
                frame.frame.data.tobytes(), webFrontend.config.LIVEKIT_SAMPLE_RATE)
            if not triggered:
                ring_buffer.append((byteFrame, isSpeech))
                num_voiced = len([f for f, speech in ring_buffer if speech])
                if num_voiced > 0.9 * maxlen:
                    triggered = True
                    voiced_frames.extend(
                        [f for f, speech in ring_buffer if speech])
                    ring_buffer = []
            else:
                voiced_frames.append(byteFrame)
                ring_buffer.append((byteFrame, isSpeech))
                num_unvoiced = len(
                    [f for f, speech in ring_buffer if not speech])
                if num_unvoiced > 0.9 * maxlen:
                    triggered = False
                    bs.append(b''.join(f for f in voiced_frames))

                    def proc(b: bytes):
                        temp = self.dataProvider.tempFilePathProvider('wav')
                        with open(temp, 'wb') as f:
                            f.write(b)

                        glmFile = google.generativeai.upload_file(temp)
                        os.remove(temp)
                        return glmFile
                    files = [proc(b) for b in bs]
                    self.chat(files)
                    ring_buffer = []
                    voiced_frames = []

    async def receiveVideoStream(self, stream: livekit.rtc.VideoStream) -> None:
        """
        Receive video stream from other user.

        Args:
            stream (livekit.rtc.VideoStream): video stream

        Returns:
            None
        """
        async for frame in stream:
            self.currentImageFrame = frame.frame

    def start(self, botToken: str) -> None:
        """
        Start the hoster of chat session.

        Returns:
            None
        """
        async def startChat():
            self.chatRoom = livekit.rtc.Room()
            await self.chatRoom.connect(webFrontend.config.LIVEKIT_API_URL, botToken)

            @self.chatRoom.on("track_subscribed")
            def on_track_subscribed(track: livekit.rtc.Track):
                if track.kind == livekit.rtc.TrackKind.KIND_AUDIO:
                    stream = livekit.rtc.AudioStream(track)
                    asyncio.ensure_future(self.VAD(stream))
                elif track.kind == livekit.rtc.TrackKind.KIND_VIDEO:
                    stream = livekit.rtc.AudioStream(track)
                    asyncio.ensure_future(self.receiveVideoStream(stream))

            @self.chatRoom.on("participant_connected")
            def on_participant_connected(participant: livekit.rtc.RemoteParticipant):
                print(f"participant connected: {
                      participant.identity} {participant.sid}")

            # publish track
            audioSource = livekit.rtc.AudioSource(
                webFrontend.config.LIVEKIT_SAMPLE_RATE, 1)
            self.broadcastAudioTrack = livekit.rtc.LocalAudioTrack.create_audio_track(
                "stream_track", audioSource)
            publication = await self.chatRoom.local_participant.publish_track(
                self.broadcastAudioTrack, livekit.rtc.TrackPublishOptions(source=livekit.rtc.TrackSource.SOURCE_MICROPHONE))
            print(f"broadcast audio track published: {
                  publication.track.track_id}")

            asyncio.ensure_future(self.broadcastAudioLoop(
                source=audioSource, frequency=1000))

        asyncio.get_event_loop().run_until_complete(startChat())

    def generateEmptyAudioFrame(self) -> livekit.rtc.AudioFrame:
        """
        Generate an empty audio frame.

        Returns:
            livekit.rtc.AudioFrame: empty audio frame
        """
        return livekit.rtc.AudioFrame(
            num_channels=1,
            data=b'\x00' * 160,
            sample_rate=webFrontend.config.LIVEKIT_SAMPLE_RATE
        )

    def fetchBroadcastMission(self) -> None:
        if len(self.broadcastMissions) == 0:
            self.currentBroadcastMission = None
        else:
            r = self.dataProvider.convertModelResponseToTTSInput(
                [self.broadcastMissions.get()], self.ttsService['reference_audios'])[0]
            refAudio = self.dataProvider.getReferenceAudioByName(
                self.ttsServiceId, r['emotion'])
            if refAudio is None:
                raise exceptions.ReferenceAudioNotFound(
                    f"Reference audio for emotion {r['emotion']} not found")
            self.currentBroadcastMission = av.open(self.GPTSoVITsAPI.tts(
                refAudio['path'], refAudio['text'], r['text'], refAudio['language']).raw)
        return self.currentBroadcastMission

    async def broadcastAudioLoop(self, source: livekit.rtc.AudioSource, frequency: int):
        while True:
            if self.fetchBroadcastMission() is None:
                await source.capture_frame(self.generateEmptyAudioFrame())
            else:
                frame: Optional[av.AudioFrame] = None
                async for frame in self.currentBroadcastMission.decode(audio=0):
                    livekitFrame = livekit.rtc.AudioFrame(
                        frame.to_ndarray().tobytes(),
                        frame.sample_rate,
                        num_channels=1, samples_per_channel=480).remix_and_resample(webFrontend.config.LIVEKIT_SAMPLE_RATE, 1)

                    await source.capture_frame(livekitFrame)

    def chatPluginGetUserMedia(self) -> glm.File:
        """
        Get image of user's camera or sharing screen. Use it when user want you to know about the content of his camera or screen or 
        your response is related to the content of the camera or screen.

        Returns:
            glm.File: Image file of user's camera or sharing screen.
        """

        if self.currentImageFrame is None:
            raise exceptions.NoUserMediaFound(
                f"No image frame found for {self.charName}")

        img = self.currentImageFrame.convert(
            livekit.rtc.VideoBufferType.RGBA).data.tobytes()
        img_np = numpy.frombuffer(img, dtype=numpy.uint8).reshape(
            self.currentImageFrame.height,
            self.currentImageFrame.width,
            4
        )
        encoded, buffer = cv2.imencode('.jpg', img_np)
        temp = self.dataProvider.tempFilePathProvider('jpg')
        with open(temp, 'wb') as f:
            f.write(buffer)

        glmFile = google.generativeai.upload_file(temp)
        os.remove(temp)
        return glmFile

    def terminateSession(self) -> None:
        """
        Terminate the chat session.
        """
        async def f():
            await self.chatRoom.disconnect()
            self.bot.terminateChat()

        asyncio.get_event_loop().run_until_complete(f())


class chatbotManager:
    def __init__(self, dProvider: dataProvider.DataProvider) -> None:
        """
        Initialize chatbot manager

        Args:
            dProvider (dataProvider.DataProvider): data provider object
        """

        # normal chat session pool
        self.pool = {}
        # real time streaming session pool
        self.rtPool = {}

        self.dataProvider = dProvider
        self.clearTh = threading.Thread(
            target=self.clearSessonThread, args=())
        self.clearTh.start()

    def createSession(self, charName: str) -> str:
        """
        Create a new chat session for a character

        Args:
            charName (str): character name

        Returns:
            str: session name
        """
        # chat session reusing
        for i in self.pool.keys():
            if self.pool[i]['charName'] == charName:
                return i

        sessionName = uuid.uuid4().hex
        sessionChatbot = instance.Chatbot(memory.Memory(
            self.dataProvider, charName), self.dataProvider.getUserName())
        self.pool[sessionName] = {
            'expireTime': time.time() + 60 * 5,
            'bot': sessionChatbot,
            'history': [],
            'charName': charName
        }

        return sessionName

    def checkIfRtSessionExist(self, sessionName: str) -> bool:
        """
        Check if a real time session exists for a character

        Args:
            sessionName (str): session name

        Returns:
            bool: True if the session exists, False otherwise
        """
        return sessionName in self.rtPool

    def createRtSession(self, charName: str, sessionName: str, voiceSession: VoiceChatSession) -> str:
        """
        Create a new real time chat session for a character

        Args:
            charName (str): character name
            sessionName (str): session name

        Raises:
            exceptions.SessionHasAlreadyExist: if there's already a real time session for the character

        Returns:
            function: A callback to set current user sharing media frame.
        """
        # if there's a real time session, throw 500
        for i in self.rtPool.keys():
            if self.rtPool[i]['charName'] == charName:
                raise exceptions.SessionHasAlreadyExist(
                    f"Session {i} already exists")

        # create a new real time session
        self.rtPool[sessionName] = {
            'charName': charName,
            'voiceChatSession': voiceSession
        }

        return sessionName

    def getSession(self, sessionName: str, doRenew: bool = True) -> instance.Chatbot:
        if sessionName in self.pool:
            r: instance.Chatbot = self.pool[sessionName]['bot']
            if doRenew:
                self.pool[sessionName]['expireTime'] = time.time() + 60 * 5
                print('Session renewed: ',
                      self.pool[sessionName]['expireTime'])
            return r
        else:
            raise exceptions.SessionNotFound(
                f'{__name__}: Session {sessionName} not found or expired')

    def getRtSession(self, sessionName: str) -> VoiceChatSession:
        """
        Get a real time chat session

        Args:
            sessionName (str): session name

        Raises:
            exceptions.SessionNotFound: if the session is not found or expired

        Returns:
            instance.Chatbot: chatbot object for the real time session
        """
        if sessionName in self.rtPool:
            return self.rtPool[sessionName]['voiceChatSession']
        else:
            raise exceptions.SessionNotFound(
                f'{__name__}: Real time chat session {sessionName} not found or expired')

    def terminateRtSession(self, sessionName: str) -> None:
        """
        Terminate a real time chat session

        Args:
            sessionName (str): session name

        Raises:
            exceptions.SessionNotFound: if the session is not found or expired
        """
        if sessionName in self.rtPool:
            self.getRtSession(sessionName).terminateSession()
            del self.rtPool[sessionName]
        else:
            raise exceptions.SessionNotFound(
                f'{__name__}: Real time chat session {sessionName} not found or expired')

    def getSessionHistory(self, sessionName: str) -> list[dict[str, str | int | bool]]:
        if sessionName in self.pool:
            r: list[dict[str, str | int | bool]
                    ] = self.pool[sessionName]['history']
            return r
        else:
            raise exceptions.SessionNotFound(
                f'{__name__}: Session {sessionName} not found or expired')

    def appendToSessionHistory(self, sessionName: str, newMsg: list[dict[str, str | int | bool]]) -> None:
        if sessionName in self.pool:
            self.pool[sessionName]['history'] += newMsg
            return None
        else:
            raise exceptions.SessionNotFound(
                f'{__name__}: Session {sessionName} not found or expired')

    def beginChat(self, sessionName: str, msgChain: list[str]) -> list[dict[str, str | int | bool]]:
        if sessionName in self.pool:
            f = self.dataProvider.parseMessageChain(msgChain)
            self.appendToSessionHistory(sessionName, f)
            plain = self.getSession(
                sessionName).begin(self.dataProvider.convertMessageHistoryToModelInput(f))

            result = []

            print('TTS available: ', 'True' if (TokenCounter(plain) < 621 and self.getSession(
                sessionName).memory.getCharTTSServiceId() != 0) else 'False')
            if TokenCounter(plain) < 621 and self.getSession(sessionName).memory.getCharTTSServiceId() != 0 and random.randint(0, 1) == 0:
                # remove all emojis in `plain`
                plain = removeEmojis(plain)

                result = self.dataProvider.convertModelResponseToAudio(
                    self.getSession(
                        sessionName).memory.getCharTTSServiceId(),
                    self.dataProvider.parseModelResponse(plain),
                    # self.getSession(sessionName).memory.getAvailableStickers()
                )
            else:
                plain = EmojiToStickerInstrctionModel(plain, ''.join(
                    f'({i}) ' for i in self.getSession(sessionName).getAvailableStickers()))
                # further remove processing of emojis
                plain = removeEmojis(plain)
                for i in self.getSession(sessionName).getAvailableStickers():
                    # fuck unicode parentheses
                    plain = plain.replace(f'（{i}）', f'({i})')
                    # I hate gemini-1.0
                    plain = plain.replace(f':{i}:', f'({i})')
                result = self.dataProvider.parseModelResponse(plain)

            self.appendToSessionHistory(sessionName, result)

            self.dataProvider.saveChatHistory(
                self.pool[sessionName]['charName'], f + result)
            return result
        else:
            raise exceptions.SessionNotFound(
                f'{__name__}: Session {sessionName} not found or expired')

    def sendMessage(self, sessionName: str, msgChain: list[str]) -> list[dict[str, str | int | bool]]:
        if sessionName in self.pool:
            f = self.dataProvider.parseMessageChain(msgChain)
            self.appendToSessionHistory(sessionName, f)

            result = None
            retries = 0
            while result == None:
                try:
                    plain = self.getSession(
                        sessionName).chat(userInput=self.dataProvider.convertMessageHistoryToModelInput(f))

                    if TokenCounter(plain) < 621 and self.getSession(sessionName).memory.getCharTTSServiceId() != 0 and random.randint(0, 1) == 0:
                        # remove all emojis in `plain`
                        plain = removeEmojis(plain)

                        result = self.dataProvider.convertModelResponseToAudio(
                            self.getSession(
                                sessionName).memory.getCharTTSServiceId(),
                            self.dataProvider.parseModelResponse(plain),
                            # self.getSession(sessionName).memory.getAvailableStickers()
                        )
                    else:
                        plain = EmojiToStickerInstrctionModel(plain, ''.join(
                            f'({i}) ' for i in self.getSession(sessionName).getAvailableStickers()))

                        result = self.dataProvider.parseModelResponse(plain)

                except Exception as e:
                    retries += 1
                    if retries > dataProvider.config.MAX_CHAT_RETRY_COUNT:
                        raise exceptions.MaxRetriesExceeded(
                            f'{__name__}: Invalid response. Max retries exceeded.')
                    continue
            self.appendToSessionHistory(sessionName, result)
            self.dataProvider.saveChatHistory(
                self.pool[sessionName]['charName'], f + result)
            return result
        else:
            raise exceptions.SessionNotFound(
                f'{__name__}: Session {sessionName} not found or expired')

    def terminateSession(self, sessionName: str) -> None:
        if sessionName in self.pool:
            charName = self.getSession(sessionName, False).memory.getCharName()
            self.getSession(sessionName, False).terminateChat()
            del self.pool[sessionName]
            print(f'Terminated session {sessionName}')
        else:
            raise exceptions.SessionNotFound(
                f'{__name__}: Session {sessionName} not found or expired')

    def clearSessonThread(self) -> None:
        while True:
            for i in [k for k in self.pool.keys()]:
                print(i, time.time(), self.pool[i]['expireTime'])
                if time.time() > self.pool[i]['expireTime']:
                    self.terminateSession(i)
            # do not clean real time session pool until users terminate it themselves

            time.sleep(1 * 60)
