from ast import parse
import asyncio
import contextlib
import io
import mimetypes
from os import remove
import os
import queue
import re
import threading
from typing import Optional
import wave

import av
from cv2 import broadcast
import cv2
import livekit.api
import livekit.rtc
from mirai import Voice
from numpy import byte, char
import numpy
from pyparsing import Opt
import requests
import noisereduce
# import sympy
from GPTSoVits import GPTSoVitsAPI
# from asyncore import loop
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
            dataProvider, charName, True), dataProvider.getUserName(), [self.chatPluginGetUserMedia])
        self.chatRoom: Optional[livekit.rtc.Room] = None
        self.dataProvider = dataProvider
        self.currentImageFrame: Optional[livekit.rtc.VideoFrame] = None
        self.broadcastAudioTrack: Optional[livekit.rtc.AudioTrack] = None
        self.broadcastMissions: queue.Queue[dict[str,
                                                 str | int | bool]] = queue.Queue()
        self.currentBroadcastMission: Optional[av.InputContainer |
                                               av.OutputContainer] = None
        self.ttsServiceId = self.bot.memory.getCharTTSServiceId()
        self.ttsService = self.dataProvider.getGPTSoVitsService(
            self.ttsServiceId)
        self.GPTSoVITsAPI = GPTSoVitsAPI(self.ttsService['url'])
        self.vadModel = webrtcvad.Vad(3)
        self.chat_lock = threading.Lock()
        self.message_queue: list[glm.File] = []
        self.terminateSessionCallback = None
        self.loop: asyncio.AbstractEventLoop = None
        print('initialized voice chat session')

    async def ttsInvocation(self, parsedResponse: dict[str, str | int | bool]) -> 'av.InputContainer':
        """
        Invoke GPT-SoVITs TTS service to generate audio file for the parsed response.

        Args:
            parsedResponse (dict[str, str | int | bool]): parsed response from the chatbot

        Raises:
            exceptions.ReferenceAudioNotFound: Reference audio for emotion not found.

        Returns:
            'av.InputContainer' | 'av.OutputContainer': audio file for the parsed response.
        """
        r = self.dataProvider.convertModelResponseToTTSInput(
            [parsedResponse], self.ttsService['reference_audios'])[0]
        refAudio = self.dataProvider.getReferenceAudioByName(
            self.ttsServiceId, r['emotion'])
        if refAudio is None:
            raise exceptions.ReferenceAudioNotFound(
                f"Reference audio for emotion {r['emotion']} not found")
        return av.open(self.GPTSoVITsAPI.tts(
            refAudio['path'], refAudio['text'], r['text'], refAudio['language']).raw)

    async def chat(self, audios: list[glm.File]) -> None:
        """
        Send audio files to chatbot and retrive response as broadcast missions.

        Args:
            audios (list[glm.File]): list of audio files

        Returns:
            None
        """

        self.message_queue.extend(audios)
        if self.chat_lock.locked():
            print('wait for next round of sending')
            pass
        else:
            resp = []
            # not to use self.bot.chat here cuz we've already uploaded the files.
            if self.bot.inChatting:
                resp = self.bot.llm.chat(self.message_queue)
            else:
                resp = self.bot.llm.initiate(self.message_queue)
                self.bot.inChatting = True
            print('raw response:', resp)
            for i in self.dataProvider.parseModelResponse(resp):
                self.broadcastMissions.put(i)
            self.message_queue = []

    async def VAD(self, stream: livekit.rtc.AudioStream, mimeType: str) -> None:
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
        maxlen = 60
        triggered = False
        ext = mimetypes.guess_extension(mimeType)
        print('using audio extension:', ext)
        if ext is None:
            raise exceptions.UnsupportedMimeType(
                f"Unsupported audio mime type: {mimeType}")
            
        last_sec = time.time()
        last_sec_frames = 0
        async for frame in stream:

            # avFrame = av.AudioFrame(format='s16', layout='mono', samples=frame.frame.samples)
            last_sec_frames += 1
            if time.time() - last_sec > 1:
                last_sec = time.time()
                print(f"last second: {last_sec_frames} frames")
                last_sec_frames = 0
                print('processing frame')

            """
            for i in frame.frame.data:
                # reduce the loudness of the audio signal
                # print(i)
                i = i * 0.8
            """

            """
            audio_data = numpy.frombuffer(frame.frame.data.tobytes(), dtype=numpy.int16)
            nyquist_freq = frame.frame.sample_rate / 2

            # Create bandpass filter for voice range (80Hz - 3kHz)
            low_normalized_cutoff = 80 / nyquist_freq
            high_normalized_cutoff = 3000 / nyquist_freq
            b, a = scipy.signal.butter(4, [low_normalized_cutoff, high_normalized_cutoff], btype='band')  

            filtered_data = scipy.signal.filtfilt(b, a, audio_data)
            
            normalized_cutoff = 1000 / nyquist_freq
            b, a = scipy.signal.butter(4, normalized_cutoff, btype='low', analog=False)
            # filtered_data = lfilter(b, a, filtered_data)
            """

            # this motherfking method reduced at least 40% performance, when using torch, it's even poorer
            filtered_data = noisereduce.reduce_noise(y=frame.frame.data, sr=frame.frame.sample_rate, n_std_thresh_stationary=1.0, stationary=True, use_torch=False, device='cpu')
            # filtered_data = frame.frame.data
            # print(len(frame.frame.data.tobytes()), len(
                # audio_data.tobytes()), len(filtered_data.tobytes()))
                
            byteFrame = filtered_data.astype(numpy.int16).tobytes()
            # print('processing frame')

            isSpeech = self.vadModel.is_speech(
                byteFrame, frame.frame.sample_rate)
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
                    print('what the heck')

                    def proc(b: bytes):
                        temp = self.dataProvider.tempFilePathProvider('wav')

                        def write_wave(path: str, audio: bytes):
                            with contextlib.closing(wave.open(path, 'wb')) as f:
                                f.setnchannels(frame.frame.num_channels)
                                f.setsampwidth(2)
                                f.setframerate(frame.frame.sample_rate)
                                f.writeframes(audio)

                        write_wave(temp, b)

                        print(f"uploading {temp}")
                        # glmFile = google.generativeai.upload_file(temp)
                        # os.remove(temp)
                        # return glmFile
                        # return 1
                        return temp

                    async def proc_wrapper(proc_bs: list[bytes]):
                        files = [proc(b) for b in proc_bs]
                        print(f'uploaded audios: {files}')
                        # await self.chat(files)

                    asyncio.ensure_future(proc_wrapper(bs))

                    ring_buffer = []
                    voiced_frames = []
                    bs = []

    async def receiveVideoStream(self, stream: livekit.rtc.VideoStream) -> None:
        """
        Receive video stream from other user.

        Args:
            stream (livekit.rtc.VideoStream): video stream

        Returns:
            None
        """
        path = self.dataProvider.tempFilePathProvider('jpg')

    async def start(self, botToken: str, loop: asyncio.AbstractEventLoop) -> None:
        """
        Start the hoster of chat session.

        Returns:
            None
        """

        print('preparing to start chat...')
        self.loop = loop
        self.chatRoom = livekit.rtc.Room(loop)

        @self.chatRoom.on("track_subscribed")
        def on_track_subscribed(track: livekit.rtc.Track, publication: livekit.rtc.RemoteTrackPublication, participant: livekit.rtc.RemoteParticipant):
            print(f"track subscribed: {publication.sid}")
            if track.kind == livekit.rtc.TrackKind.KIND_VIDEO:
                print('running video stream...')
                asyncio.ensure_future(self.receiveVideoStream(
                    livekit.rtc.VideoStream(track)))
            elif track.kind == livekit.rtc.TrackKind.KIND_AUDIO:
                print('running voice activity detection...')
                asyncio.ensure_future(
                    self.VAD(livekit.rtc.AudioStream(track), publication.mime_type))

        @self.chatRoom.on("track_unsubscribed")
        def on_track_unsubscribed(track: livekit.rtc.Track, publication: livekit.rtc.RemoteTrackPublication, participant: livekit.rtc.RemoteParticipant):
            print(f"track unsubscribed: {publication.sid}")

        @self.chatRoom.on("participant_connected")
        def on_participant_connected(participant: livekit.rtc.RemoteParticipant):
            print(f"participant connected: {
                participant.identity} {participant.sid}")

        @self.chatRoom.on("participant_disconnected")
        def on_participant_disconnected(participant: livekit.rtc.RemoteParticipant):
            print(
                f"participant disconnected: {
                    participant.sid} {participant.identity}"
            )

            # async def f():
            # await self.chatRoom.disconnect()
            self.terminateSession()
            # loop.stop()
            # loop.stop()

            # asyncio.ensure_future(f())

        @self.chatRoom.on("connected")
        def on_connected() -> None:
            print("connected")

        print('connecting to room...')
        await self.chatRoom.connect(f"ws://{webFrontend.config.LIVEKIT_API_EXTERNAL_URL}", botToken)

        # publish track
        audioSource = livekit.rtc.AudioSource(
            webFrontend.config.LIVEKIT_SAMPLE_RATE, 1)
        self.broadcastAudioTrack = livekit.rtc.LocalAudioTrack.create_audio_track(
            "stream_track", audioSource)
        # we don't support audio/red format
        publication = await self.chatRoom.local_participant.publish_track(
            self.broadcastAudioTrack, livekit.rtc.TrackPublishOptions(source=livekit.rtc.TrackSource.SOURCE_MICROPHONE, red=False))
        print(f"broadcast audio track published: {
            publication.track.name}")

        asyncio.ensure_future(self.broadcastAudioLoop(
            source=audioSource, frequency=1000))

    def generateEmptyAudioFrame(self) -> livekit.rtc.AudioFrame:
        """
        Generate an empty audio frame.

        Returns:
            livekit.rtc.AudioFrame: empty audio frame
        """
        amplitude = 32767  # for 16-bit audio
        samples_per_channel = 480  # 10ms at 48kHz
        time = numpy.arange(samples_per_channel) / \
            webFrontend.config.LIVEKIT_SAMPLE_RATE
        total_samples = 0
        audio_frame = livekit.rtc.AudioFrame.create(
            webFrontend.config.LIVEKIT_SAMPLE_RATE, 1, samples_per_channel)
        audio_data = numpy.frombuffer(audio_frame.data, dtype=numpy.int16)
        time = (total_samples + numpy.arange(samples_per_channel)) / \
            webFrontend.config.LIVEKIT_SAMPLE_RATE
        wave = numpy.int16(0)
        numpy.copyto(audio_data, wave)
        # print('done1')
        return audio_frame

    def fetchBroadcastMission(self) -> None:
        if self.broadcastMissions.empty():
            # self.currentBroadcastMission = None
            self.currentBroadcastMission = av.open(
                "./temp/wdnmd.wav", "r")
        else:
            # self.currentBroadcastMission = self.broadcastMissions.get()
            pass
        return self.currentBroadcastMission

    async def broadcastAudioLoop(self, source: livekit.rtc.AudioSource, frequency: int):
        print('broadcasting audio...')
        while True:
            if self.fetchBroadcastMission() is None:
                print('capturing empty audio frame...')
                await source.capture_frame(self.generateEmptyAudioFrame())
                # print('done2')
            else:
                frame: Optional[av.AudioFrame] = None
                start = time.time()
                count = 0
                for frame in self.currentBroadcastMission.decode(audio=0):
                    # print(frame.sample_rate, frame.rate, frame.samples, frame.time_base, frame.dts, frame.pts, frame.time, len(frame.layout.channels), len(frame.to_ndarray().astype(numpy.int16).tobytes()), len(
                    # frame.layout.channels), [i for i in frame.side_data.keys()])
                    try:
                        # sizeof(int16) =
                        # print out attrs of livekitFrame when initializing it.
                        # print(frame.samples * 2, len(frame.to_ndarray().astype(numpy.int16).tobytes()))
                        resampledFrame = av.AudioResampler(
                            format='s16', layout='mono', rate=webFrontend.config.LIVEKIT_SAMPLE_RATE).resample(frame)[0]
                        # print(resampledFrame.samples * 2, len(resampledFrame.to_ndarray().astype(numpy.int16).tobytes()))
                        livekitFrame = livekit.rtc.AudioFrame(
                            data=resampledFrame.to_ndarray().astype(numpy.int16).tobytes(),
                            sample_rate=resampledFrame.sample_rate,
                            num_channels=len(resampledFrame.layout.channels),
                            samples_per_channel=resampledFrame.samples // len(resampledFrame.layout.channels),)
                        # print(livekitFrame.sample_rate, livekitFrame.num_channels, livekitFrame.samples_per_channel, len(livekitFrame.data))
                    except Exception as e:
                        raise e
                        # if there's problem with the frame, skip it and continue to the next one.
                        print('Error processing frame, skipping it.')
                        continue
                    # while time.time() < future:
                    await source.capture_frame(livekitFrame)
                    # await asyncio.sleep(0.0001)

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
            livekit.rtc.VideoBufferType.BGRA).data.tobytes()
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

        FIXME: it will only be triggered when other events received first. strange
        """
        # self.bot.terminateChat()
        self.terminateSessionCallback()

        async def f():
            print('terminating chat session...')
            self.bot.terminateChat()
            # self.terminateSessionCallback()
            await self.chatRoom.disconnect()

        print(asyncio.get_event_loop(), self.loop)
        # self.loop.stop()
        asyncio.ensure_future(f())


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
                    f"Session for {charName} already exists")

        def terminateCallback():
            print(f'Terminating real time session {sessionName}')
            self.terminateRtSession(sessionName)

        voiceSession.terminateSessionCallback = terminateCallback
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
            # self.getRtSession(sessionName).terminateSession()
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
