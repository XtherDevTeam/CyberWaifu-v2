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
import cv2
import livekit.api
import livekit.rtc
import numpy
# import sympy
from GPTSoVits import GPTSoVitsAPI
import SileroVAD
import dataProvider
import logger
import memory
import uuid
import time
import instance
import exceptions
import random
import livekit
import google.ai.generativelanguage as glm
import webFrontend.config
import google.generativeai

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
            dataProvider, charName, True), dataProvider.getUserName())
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
        self.GPTSoVITsAPI = GPTSoVitsAPI(
            self.ttsService['url'], isTTSv3=True, ttsInferYamlPath=self.ttsService['ttsInferYamlPath'])
        self.chat_lock = threading.Lock()
        self.message_queue: list[glm.File] = []
        self.terminateSessionCallback = None
        self.loop: asyncio.AbstractEventLoop = None
        self.broadcastingThread: threading.Thread = None
        self.connected: bool = False
        logger.Logger.log('initialized voice chat session')

    def runBroadcastingLoop(self, audioSource) -> None:
        """
        Start the loop for broadcasting missions.

        Returns:
            None
        """
        logger.Logger.log('starting broadcasting loop')
        new_loop = asyncio.new_event_loop()
        new_loop.run_until_complete(self.broadcastAudioLoop(audioSource))

    def convertModelResponseToTTSInput(self, parsedResponse: dict[str, str | int | bool]) -> list[dict[str, str | int | bool]]:
        """
        A method specifially for VoiceChat prompt.
        Convert the parsed response from the chatbot to TTS input.

        Args:
            parsedResponse (dict[str, str | int | bool]): parsed response from the chatbot

        Returns:
            list[dict[str, str | int | bool]]: list of TTS input
        """
        for i in parsedResponse:
            emotion = i['text'][0:i['text'].find(':')]
            text = i['text'][i['text'].find(':')+1:]
            i['emotion'] = emotion
            i['text'] = text

        return parsedResponse

    def ttsInvocation(self, parsedResponse: dict[str, str | int | bool]) -> None:
        """
        Invoke GPT-SoVITs TTS service to generate audio file for the parsed response.

        Args:
            parsedResponse (dict[str, str | int | bool]): parsed response from the chatbot

        Raises:
            exceptions.ReferenceAudioNotFound: Reference audio for emotion not found.

        Returns:
            None
        """
        r = self.convertModelResponseToTTSInput(parsedResponse)

        for i in r:
            refAudio = self.dataProvider.getReferenceAudioByName(
                self.ttsServiceId, i['emotion'])
            if refAudio is None:
                logger.Logger.log(f"Reference audio for emotion {
                                  i['emotion']} not found")
                # do not raise exception here, cuz we don't want to stop the session.
                return
            self.broadcastMissions.put(av.open(self.GPTSoVITsAPI.build_tts_v3_request(
                refAudio['path'], refAudio['text'], i['text'], refAudio['language'])))

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
            logger.Logger.log('wait for next round of sending')
            pass
        else:
            curLen = len(self.message_queue)
            await asyncio.sleep(0.5)
            if len(self.message_queue) != curLen:
                # new message arrived, skip this round
                return
            resp = []
            # not to use self.bot.chat here cuz we've already uploaded the files.
            if self.bot.inChatting:
                resp = self.bot.llm.chat(self.message_queue)
            else:
                resp = self.bot.llm.initiate(self.message_queue)
                self.bot.inChatting = True

            if 'OPT_GetUserMedia' in resp:
                logger.Logger.log('getting user media')
                resp = self.bot.llm.chat([self.getUserMedia()])
                
            resp = removeEmojis(resp)
            for i in self.bot.getAvailableStickers():
                # fuck unicode parentheses
                resp = resp.replace(f'({i})', f'')
                resp = resp.replace(f'（{i}）', f'')
                # I hate gemini-1.0
                resp = resp.replace(f':{i}:', f'')
                
            logger.Logger.log(f"chat response: {resp}")

            self.ttsInvocation(self.dataProvider.parseModelResponse(resp, isRTVC=True))

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
        logger.Logger.log('using audio extension:', ext)
        if ext is None:
            raise exceptions.UnsupportedMimeType(
                f"Unsupported audio mime type: {mimeType}")

        frames = 0
        last_sec = time.time()
        last_sec_frames = 0
        last_frame: list[livekit.rtc.AudioFrame] = []
        async for frame in stream:
            if not self.connected:
                break

            last_sec_frames += 1
            frames += 1

            if time.time() - last_sec > 1:
                last_sec = time.time()
                logger.Logger.log(f"last second: {last_sec_frames} frames")
                last_sec_frames = 0
                # logger.Logger.log('processing frame')

            # this motherfking method reduced at least 40% performance, when using torch, it's even poorer
            # filtered_data = noisereduce.reduce_noise(y=frame.frame.data, sr=frame.frame.sample_rate, n_std_thresh_stationary=1.0, stationary=True, use_torch=False, device='cpu')
            # filtered_data = frame.frame.data
            # logger.Logger.log(len(frame.frame.data.tobytes()), len(
                # audio_data.tobytes()), len(filtered_data.tobytes()))

            if frames % 4 == 0:
                # logger.Logger.log('40ms refresh')
                pass
            else:
                # last_frame = frame.frame
                last_frame.append(frame.frame)
                # logger.Logger.log('refreshing buffer', last_frame)
                continue

            rb = b''
            for i in last_frame:
                rb += i.data.tobytes()
            rb += frame.frame.data.tobytes()
            last_frame = []

            numpy_data = numpy.frombuffer(rb, dtype=numpy.int16)

            # filtered_data = self.signal_filter(y=numpy_data)

            byteFrame = numpy_data.astype(numpy.int16).tobytes()
            # wholeFrame = livekit.rtc.AudioFrame(
            # data=byteFrame, sample_rate=frame.frame.sample_rate, samples_per_channel=frame.frame.samples_per_channel, num_channels=frame.frame.num_channels)
            # logger.Logger.log(f"frame len: {len(wholeFrame.data)}")

            isSpeech = SileroVAD.SileroVAD.predict(
                numpy_data, frame.frame.sample_rate)
            # logger.Logger.log(f"is speech: {isSpeech}")
            isSpeech = isSpeech > 0.7

            if not triggered:
                ring_buffer.append((byteFrame, isSpeech))
                num_voiced = len([f for f, speech in ring_buffer if speech])
                if num_voiced > 0.8 * maxlen:
                    triggered = True
                    voiced_frames.extend(
                        [f for f, speech in ring_buffer if speech])
                    ring_buffer = []
            else:
                voiced_frames.append(byteFrame)
                ring_buffer.append((byteFrame, isSpeech))
                num_unvoiced = len(
                    [f for f, speech in ring_buffer if not speech])
                if num_unvoiced > 0.8 * maxlen:
                    triggered = False
                    bs.append(b''.join(f for f in voiced_frames))
                    logger.Logger.log('what the heck')

                    def proc(b: bytes):
                        temp = self.dataProvider.tempFilePathProvider('wav')

                        def write_wave(path: str, audio: bytes):
                            with contextlib.closing(wave.open(path, 'wb')) as f:
                                f.setnchannels(frame.frame.num_channels)
                                f.setsampwidth(2)
                                f.setframerate(frame.frame.sample_rate)
                                f.writeframes(audio)

                        write_wave(temp, b)

                        logger.Logger.log(f"uploading {temp}")
                        glmFile = google.generativeai.upload_file(temp)
                        # self.broadcastMissions.put(av.open(temp))
                        os.remove(temp)
                        return glmFile
                        # return 1
                        # return temp

                    async def proc_wrapper(proc_bs: list[bytes]):
                        files = [proc(b) for b in proc_bs]
                        logger.Logger.log(f'uploaded audios: {files}')
                        await self.chat(files)

                    def thread_wrapper(bs: list[bytes]):
                        loop = asyncio.new_event_loop()
                        x = []
                        x.extend(bs)
                        loop.run_until_complete(proc_wrapper(x))
                        loop.close()
                        logger.Logger.log('I died')

                    threading.Thread(target=thread_wrapper, args=(bs,)).start()

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
        async for frame in stream:
            if not self.connected:
                break
            self.currentImageFrame = frame.frame

    async def start(self, botToken: str, loop: asyncio.AbstractEventLoop) -> None:
        """
        Start the hoster of chat session.

        Returns:
            None
        """

        logger.Logger.log('preparing to start chat...')
        self.loop = loop
        self.chatRoom = livekit.rtc.Room(loop)
        self.connected = True

        @self.chatRoom.on("track_subscribed")
        def on_track_subscribed(track: livekit.rtc.Track, publication: livekit.rtc.RemoteTrackPublication, participant: livekit.rtc.RemoteParticipant):
            logger.Logger.log(f"track subscribed: {publication.sid}")
            if track.kind == livekit.rtc.TrackKind.KIND_VIDEO:
                logger.Logger.log('running video stream...')
                asyncio.ensure_future(self.receiveVideoStream(
                    livekit.rtc.VideoStream(track)))
            elif track.kind == livekit.rtc.TrackKind.KIND_AUDIO:
                logger.Logger.log('running voice activity detection...')
                asyncio.ensure_future(
                    self.VAD(livekit.rtc.AudioStream(track), publication.mime_type))

        @self.chatRoom.on("track_unsubscribed")
        def on_track_unsubscribed(track: livekit.rtc.Track, publication: livekit.rtc.RemoteTrackPublication, participant: livekit.rtc.RemoteParticipant):
            logger.Logger.log(f"track unsubscribed: {publication.sid}")

        @self.chatRoom.on("participant_connected")
        def on_participant_connected(participant: livekit.rtc.RemoteParticipant):
            logger.Logger.log(f"participant connected: {
                participant.identity} {participant.sid}")

        @self.chatRoom.on("participant_disconnected")
        def on_participant_disconnected(participant: livekit.rtc.RemoteParticipant):
            logger.Logger.log(
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
            logger.Logger.log("connected")

        logger.Logger.log('connecting to room...')
        await self.chatRoom.connect(f"wss://{webFrontend.config.LIVEKIT_API_EXTERNAL_URL}", botToken)

        # publish track
        audioSource = livekit.rtc.AudioSource(
            webFrontend.config.LIVEKIT_SAMPLE_RATE, 1)
        self.broadcastAudioTrack = livekit.rtc.LocalAudioTrack.create_audio_track(
            "stream_track", audioSource)
        # we don't support audio/red format
        publication = await self.chatRoom.local_participant.publish_track(
            self.broadcastAudioTrack, livekit.rtc.TrackPublishOptions(source=livekit.rtc.TrackSource.SOURCE_MICROPHONE, red=False))
        logger.Logger.log(f"broadcast audio track published: {
            publication.track.name}")

        self.broadcastingThread = threading.Thread(
            target=self.runBroadcastingLoop, args=(audioSource,))
        self.broadcastingThread.start()

        logger.Logger.log('chat session started')

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
        # logger.Logger.log('done1')
        return audio_frame

    def fetchBroadcastMission(self) -> None:
        if self.broadcastMissions.empty():
            self.currentBroadcastMission = None
            # self.currentBroadcastMission = av.open(
            # "./temp/wdnmd.wav", "r")
        else:
            self.currentBroadcastMission = self.broadcastMissions.get()
            # pass
        return self.currentBroadcastMission

    async def broadcastAudioLoop(self, source: livekit.rtc.AudioSource, frequency: int = 1000):
        logger.Logger.log('broadcasting audio...')
        while self.connected:
            # logger.Logger.log(self.broadcastMissions.qsize(), 'missions in queue')
            if self.fetchBroadcastMission() is None:
                # logger.Logger.log('capturing empty audio frame...')
                await source.capture_frame(self.generateEmptyAudioFrame())
                # logger.Logger.log('done2')
            else:
                logger.Logger.log('broadcasting mission...')
                frame: Optional[av.AudioFrame] = None
                start = time.time()
                count = 0
                for frame in self.currentBroadcastMission.decode(audio=0):
                    # logger.Logger.log(frame.sample_rate, frame.rate, frame.samples, frame.time_base, frame.dts, frame.pts, frame.time, len(frame.layout.channels), len(frame.to_ndarray().astype(numpy.int16).tobytes()), len(
                    # frame.layout.channels), [i for i in frame.side_data.keys()])
                    try:
                        # logger.Logger.log out attrs of livekitFrame when initializing it.
                        # logger.Logger.log(frame.samples * 2, len(frame.to_ndarray().astype(numpy.int16).tobytes()))
                        resampledFrame = av.AudioResampler(
                            format='s16', layout='mono', rate=webFrontend.config.LIVEKIT_SAMPLE_RATE).resample(frame)[0]
                        # logger.Logger.log(resampledFrame.samples * 2, len(resampledFrame.to_ndarray().astype(numpy.int16).tobytes()))
                        livekitFrame = livekit.rtc.AudioFrame(
                            data=resampledFrame.to_ndarray().astype(numpy.int16).tobytes(),
                            sample_rate=resampledFrame.sample_rate,
                            num_channels=len(resampledFrame.layout.channels),
                            samples_per_channel=resampledFrame.samples // len(resampledFrame.layout.channels),)
                        # logger.Logger.log(livekitFrame.sample_rate, livekitFrame.num_channels, livekitFrame.samples_per_channel, len(livekitFrame.data))
                    except Exception as e:
                        # if there's problem with the frame, skip it and continue to the next one.
                        logger.Logger.log(
                            'Error processing frame, skipping it.')
                        continue
                    await source.capture_frame(livekitFrame)

    def getUserMedia(self) -> glm.File:
        """
        Get image of user's camera or sharing screen.

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
        logger.Logger.log(f"uploading {temp}", glmFile)
        os.remove(temp)
        return glmFile

    def terminateSession(self) -> None:
        """
        Terminate the chat session.

        FIXME: it will only be triggered when other events received first. strange
        """
        # self.bot.terminateChat()
        self.connected = False
        logger.Logger.log('Triggering terminate session callback')
        self.terminateSessionCallback()

        async def f():
            logger.Logger.log('terminating chat session...')
            self.bot.terminateChat()
            SileroVAD.SileroVAD.reset()
            await self.chatRoom.disconnect()

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

    def checkIfRtSessionExist(self, charName: str) -> str | None:
        """
        Check if a real time session exists for a character

        Args:
            charName (str): session name

        Returns:
            str: session name if exists, otherwise None
        """
        for i in self.rtPool:
            if self.rtPool[i]['charName'] == charName:
                return i

        return None

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
            logger.Logger.log(f'Terminating real time session {sessionName}')
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
                logger.Logger.log('Session renewed: ',
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

            logger.Logger.log('TTS available: ', 'True' if (TokenCounter(plain) < 621 and self.getSession(
                sessionName).memory.getCharTTSServiceId() != 0) else 'False')
            if TokenCounter(plain) < 621 and self.getSession(sessionName).memory.getCharTTSServiceId() != 0 and random.randint(0, 2) == 0:
                # if True:
                # remove all emojis in `plain`
                plain = removeEmojis(plain)
                for i in self.getSession(sessionName).getAvailableStickers():
                    # fuck unicode parentheses
                    plain = plain.replace(f'（{i}）', f'({i})')
                    # I hate gemini-1.0
                    plain = plain.replace(f':{i}:', f'({i})')

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

                    if TokenCounter(plain) < 621 and self.getSession(sessionName).memory.getCharTTSServiceId() != 0 and random.randint(0, 2) == 0:
                        # remove all emojis in `plain`
                        plain = removeEmojis(plain)
                        for i in self.getSession(sessionName).getAvailableStickers():
                            # fuck unicode parentheses
                            plain = plain.replace(f'（{i}）', f'({i})')
                            # I hate gemini-1.0
                            plain = plain.replace(f':{i}:', f'({i})')

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
            logger.Logger.log(f'Terminated session {sessionName}')
        else:
            raise exceptions.SessionNotFound(
                f'{__name__}: Session {sessionName} not found or expired')

    def clearSessonThread(self) -> None:
        while True:
            for i in [k for k in self.pool.keys()]:
                logger.Logger.log(i, time.time(), self.pool[i]['expireTime'])
                if time.time() > self.pool[i]['expireTime']:
                    self.terminateSession(i)
            # do not clean real time session pool until users terminate it themselves

            time.sleep(1 * 60)
