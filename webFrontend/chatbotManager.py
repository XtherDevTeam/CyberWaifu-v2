import asyncio
import base64
import contextlib
import mimetypes
import os
import pathlib
import queue
import re
import threading
from typing import Optional
import wave
import google.genai.types
import websockets.asyncio
import websockets.asyncio.client
import websockets_proxy
import google.genai
import google.genai.live
import models
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import av
import cv2
import livekit.api
import livekit.rtc
import numpy
import AIDubMiddlewareAPI
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
import webFrontend.chatPlugins
import webFrontend.config
import io
import requests
import PIL

from models import EmojiToStickerInstrctionModel, TokenCounter

import emoji



def removeEmojis(text):
    return emoji.replace_emoji(text, '')


class VoiceChatResponse():
    """
    A class for storing voice chat response as bytes.
    """

    def __init__(self, response: requests.models.Response) -> None:
        self.response = response
        self.chunked_iter = response.iter_content(chunk_size=4096) # just magic number
        self.previous_left = b''
        
    def read(self, size: int) -> bytes:
        try:
            current = next(self.chunked_iter)
            actual = self.previous_left + current
            if len(actual) > size:
                self.previous_left = actual[size:]
                return actual[:size]
            else:
                self.previous_left = b''
                return actual
        except StopIteration:
            return b''

    def close(self) -> None:
        self.response.close()



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
        join(botToken: str, roomName: str) -> None: Join the participant of chat session.
        leave() -> None: Leave the chat session.
        getUserMedia() -> dict[str, str]: Get user media (camera or screen) as inline data.
        broadcastAudioLoop(audioSource) -> None: Start the loop for broadcasting missions.
        convertModelResponseToTTSInput(parsedResponse: dict[str, str | int | bool]) -> list[dict[str, str | int | bool]]: Convert the parsed response from the chatbot to TTS input.
        ttsInvocation(parsedResponse: dict[str, str | int | bool]) -> None: Invoke GPT-SoVITs TTS service to generate audio file for the parsed response.
        messageQueuePreProcessing(messageQueue: list[str]) -> list[dict[str, str]]: Pre-process the message queue to convert audio files to inline data and remove them from the queue.
        chat(audios: list[str]) -> None: Send audio files to chatbot and retrive response as broadcast missions.
    """

    def __init__(self, sessionName: str, charName: str, dataProvider: dataProvider.DataProvider) -> None:
        self.sessionName = sessionName
        self.charName = charName
        self.bot = instance.Chatbot(memory.Memory(
            dataProvider, charName, True), dataProvider.getUserName(), rtSession=True)
        self.llmSession = None
        self.chatRoom: Optional[livekit.rtc.Room] = None
        self.dataProvider = dataProvider
        self.currentImageFrame: Optional[livekit.rtc.VideoFrame] = None
        self.broadcastAudioTrack: Optional[livekit.rtc.AudioTrack] = None
        self.broadcastMissions: queue.Queue[dict[str,
                                                 str | int | bool]] = queue.Queue()
        self.currentBroadcastMission: Optional[av.InputContainer |
                                               av.OutputContainer] = None
        self.ttsUseModel = self.bot.memory.getCharTTSUseModel()
        self.AIDubMiddlewareAPI = AIDubMiddlewareAPI.AIDubMiddlewareAPI(self.dataProvider.getGPTSoVITsMiddleware())
        self.chat_lock = threading.Lock()
        self.message_queue: list[str] = []
        self.terminateSessionCallback = None
        self.loop: asyncio.AbstractEventLoop = None
        self.audioBroadcastingThread: threading.Thread = None
        self.connected: bool = False
        self.connectionLogs: list[str] = []
        self.loggerCallbackId: None | int = None
        self.broadcastMissionCancelled: bool = False
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
        
    def runVideoBroadcastingLoop(self, videoSource) -> None:
        """
        Start the loop for broadcasting video.

        Returns:
            None
        """
        logger.Logger.log('starting video broadcasting loop')
        new_loop = asyncio.new_event_loop()
        new_loop.run_until_complete(self.broadcastVideoLoop(videoSource))

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
        for i in parsedResponse:
            # no proxy
            self.broadcastMissions.put(av.open(VoiceChatResponse(self.AIDubMiddlewareAPI.dub(i['text'], self.ttsUseModel))))
            logger.Logger.log(f"generated audio for {i['text']}")

    def messageQueuePreProcessing(self, messageQueue: list[str]) -> list[dict[str, str]]:
        """
        Pre-process the message queue to convert audio files to inline data and remove them from the queue.

        Args:
            messageQueue (list[str]): list of audio file paths

        Returns:
            list[dict[str, str]]: list of inline data objects
        """

        # just in case of which gets a list of processed queue instead of file paths
        res = [{
            'mime_type': 'audio/wav',
            'data': pathlib.Path(message).read_bytes()
        } if type(message) is str else message for message in messageQueue]
        for i in messageQueue:
            os.remove(i)
        return res

    async def chat(self, audios: list[str]) -> None:
        """
        Send audio files to chatbot and retrive response as broadcast missions.

        Args:
            audios (list[str]): list of audio file paths

        Returns:
            None
        """

        self.message_queue.extend(audios)
        print('chat invoked', len(self.message_queue))
        
        with self.chat_lock:
            if self.message_queue[0] == "Voices:":
                self.message_queue = self.message_queue[1:]
            
            self.message_queue = self.messageQueuePreProcessing(
                self.message_queue)
            self.message_queue.append(self.getUserMedia())
            self.message_queue = ["Voices:"] + self.message_queue

            resp = []
            # not to use self.bot.chat here cuz we've already uploaded the files.
            if self.bot.inChatting:
                resp = self.bot.llm.chat(self.message_queue)
            else:
                resp = self.bot.llm.initiate(self.message_queue)
                self.bot.inChatting = True

            if 'OPT_Silent' not in resp:
                resp = removeEmojis(resp)
                # use |<spliter>| to split setences
                for i in self.bot.getAvailableStickers():
                    # fuck unicode parentheses
                    resp = resp.replace(f'({i})', '|<spliter>|')
                    resp = resp.replace(f'（{i}）', '|<spliter>|')
                    # I hate gemini-1.0
                    resp = resp.replace(f':{i}:', '|<spliter>|')
                    resp = resp.replace(f'. ', '|<spliter>|')

                # capture whitespace more than 2 times in a row
                resp = re.sub(r'\s{2,}', '|<spliter>|', resp)

                logger.Logger.log(f"chat response: {resp}")

                await self.ttsInvocation(
                    self.dataProvider.parseModelResponse(resp, isRTVC=True))
            else:
                logger.Logger.log(f"NOT RESPONDING")
            self.message_queue = []


    async def VAD(self, stream: livekit.rtc.AudioStream, mimeType: str) -> None:
        """
        Deprecated.
        Voice activity detection.
        Fetch and identify each audio frame, when activity detected, save to local temporary file and upload as inline data then send to Gemini model as Input.

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
        maxlen = 45
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
                logger.Logger.log('Session terminated, stopping VAD loop')
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

            byteFrame = numpy_data.astype(numpy.int16).tobytes()

            isSpeech = SileroVAD.SileroVAD.predict(
                numpy_data, frame.frame.sample_rate)
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

                        logger.Logger.log(f"saved as {temp}")
                        return temp

                    async def proc_wrapper(proc_bs: list[bytes]):
                        files = [proc(b) for b in proc_bs]
                        logger.Logger.log(f'total: {files}')
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


    async def chatRealtime(self):
        """
        New real time chat method for gemini-2.0-flash-exp
        """
        buffer = ''
        while True:
            async for response in self.llmSession.receive():
                # recv a turn of chat
                if response.text is not None:
                    buffer += response.text
            
            if not self.connected:
                logger.Logger.log('Session terminated, stopping chatRealtime loop')
                self.bot.memory.storeMemory(self.bot.userName, buffer)
                await self.llmPreSession.__aexit__(None, None, None) # memory stored, close the session safely
                break
            
            if buffer == 'OPT_Silent':
                continue
            
            self.broadcastMissionCancelled = False
            
            resp = removeEmojis(buffer)
            # use |<spliter>| to split setences
            for i in self.bot.getAvailableStickers():
                # fuck unicode parentheses
                resp = resp.replace(f'({i})', '|<spliter>|')
                resp = resp.replace(f'（{i}）', '|<spliter>|')
                # I hate gemini-1.0
                resp = resp.replace(f':{i}:', '|<spliter>|')
                resp = resp.replace(f'. ', '|<spliter>|')
                resp = resp.replace(f'? ', '|<spliter>|')
                resp = resp.replace(f'! ', '|<spliter>|')

            # capture whitespace more than 2 times in a row
            resp = re.sub(r'\s{2,}', '|<spliter>|', resp)
            
            logger.Logger.log(f"Chat response: {resp}")

            def new_thread():
                self.ttsInvocation(self.dataProvider.parseModelResponse(resp, isRTVC=True))
                
            threading.Thread(target=new_thread).start()
            
            buffer = ''
            # await asyncio.to_thread(, self.dataProvider.parseModelResponse(resp, isRTVC=True))
                        

    async def forwardAudioStream(self, stream: livekit.rtc.AudioStream, mimeType: str) -> None:
        """
        Forward audio stream to LLM session in the session.

        Args:
            stream (livekit.rtc.AudioStream): audio stream
            mimeType (str): mime type of the audio stream

        Returns:
            None
        """
        frames = 0
        last_sec = time.time()
        last_sec_frames = 0
        limit_to_send = 100
        data_chunk = b''
        # a simple implemenation of WebRTC VAD algorithm
        ring_frame, current_count = 0, 0
        last_frame: list[livekit.rtc.AudioFrame] = []
        ext = mimetypes.guess_extension(mimeType)
        logger.Logger.log('using audio extension:', ext)
        async for frame in stream:
            if not self.connected:
                break
            last_sec_frames += 1
            frames += 1
            avFrame = av.AudioFrame.from_ndarray(numpy.frombuffer(frame.frame.remix_and_resample(16000, 1).data, dtype=numpy.int16).reshape(frame.frame.num_channels, -1), layout='mono', format='s16')
            data_chunk += avFrame.to_ndarray().tobytes()
            if frames % limit_to_send == 0:
                await self.llmSession.send({"data": data_chunk, "mime_type": "audio/pcm"})
            
                data_chunk = b''
                    
            if time.time() - last_sec > 1:
                last_sec = time.time()
                logger.Logger.log(f"forwardAudioStream: last second: {last_sec_frames} frames, num_channels: {frame.frame.num_channels}, sample_rate: {frame.frame.sample_rate}, limit_to_send: {limit_to_send}")
                last_sec_frames = 0
                
            # vad
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

            byteFrame = numpy_data.astype(numpy.int16).tobytes()

            isSpeech = SileroVAD.SileroVAD.predict(
                numpy_data, frame.frame.sample_rate)
            
            if isSpeech > 0.7:
                ring_frame += 1
            
            if ring_frame > 10:
                logger.Logger.log('Cancelling ongoing broadcast missions') 
                self.cancelOngoingBroadcast()
                current_count = 0
                ring_frame = 0
            
            current_count += 1
            if current_count > 20:
                current_count = 0
                ring_frame = 0
    
    
    def cancelOngoingBroadcast(self):
        """
        Cancel ongoing broadcast missions.

        Returns:
            None
        """
        self.broadcastMissions = queue.Queue()
        self.broadcastMissionCancelled = True
    
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
            img = frame.frame.convert(
                livekit.rtc.VideoBufferType.BGRA).data.tobytes()
            img_np = numpy.frombuffer(img, dtype=numpy.uint8).reshape(
                frame.frame.height,
                frame.frame.width,
                4
            )
            # convert to jpeg
            # resize the image so as to save the token
            scaler = frame.frame.width / 1280
            new_width, new_height = (int(
                frame.frame.width // scaler), int(frame.frame.height // scaler))
            cv2.resize(img_np, (new_width, new_height))

            encoded, buffer = cv2.imencode('.jpg', img_np)
            
            """
            temp = self.dataProvider.tempFilePathProvider('jpg')
            with open(temp, 'wb') as f:
                f.write(buffer.tobytes())
            logger.Logger.log(f"saved as {temp}")
            """
            
            await self.llmSession.send({"data": base64.b64encode(buffer.tobytes()).decode(), "mime_type": "image/jpeg"})


    async def start(self, botToken: str, loop: asyncio.AbstractEventLoop) -> None:
        """
        Start the hoster of chat session.

        Returns:
            None
        """

        logger.Logger.log('Preparing to start chat...')
        self.loop = loop
        self.chatRoom = livekit.rtc.Room(loop)
        self.connected = True
        self.loggerCallbackId = logger.Logger.registerCallback(lambda s: self.connectionLogs.append(s))

        # patch for google.genai
        if os.getenv("ALL_PROXY") is not None:
            logger.Logger.log("ALL_PROXY environment variable detected, patching google.genai.live.connect")
            proxy = websockets_proxy.Proxy.from_url(os.getenv("ALL_PROXY"))
            def fake_connect(*args, **kwargs):
                return websockets_proxy.proxy_connect(*args, proxy=proxy, **kwargs)
            google.genai.live.connect = fake_connect

        client = google.genai.Client(http_options={'api_version': 'v1alpha'})
        model_id = "gemini-2.0-flash-exp"
        config = {"response_modalities": ["TEXT"], "system_instruction": self.bot.memory.createCharPromptFromCharacter(self.bot.userName), "tools": [webFrontend.chatPlugins.getEncodedPluginList()], "temperature": 0.9}
        self.llmPreSession = client.aio.live.connect(model=model_id, config=config)
        print("Default's", id(asyncio.get_event_loop()))
        self.llmSession: google.genai.live.AsyncSession = await self.llmPreSession.__aenter__() # to simulate async context manager
        asyncio.ensure_future(self.chatRealtime())
        
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
                    self.forwardAudioStream(livekit.rtc.AudioStream(track), publication.mime_type))

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
        # audio
        audioSource = livekit.rtc.AudioSource(
            webFrontend.config.LIVEKIT_SAMPLE_RATE, 1)
        self.broadcastAudioTrack = livekit.rtc.LocalAudioTrack.create_audio_track(
            "stream_track", audioSource)
        # video
        videoSource = livekit.rtc.VideoSource(
            webFrontend.config.LIVEKIT_VIDEO_WIDTH, webFrontend.config.LIVEKIT_VIDEO_HEIGHT)
        self.broadcastVideoTrack = livekit.rtc.LocalVideoTrack.create_video_track(
            "video_track", videoSource)
        # we don't support audio/red format
        publication_audio = await self.chatRoom.local_participant.publish_track(
            self.broadcastAudioTrack, livekit.rtc.TrackPublishOptions(source=livekit.rtc.TrackSource.SOURCE_MICROPHONE, red=False))
        logger.Logger.log(f"broadcast audio track published: {
            publication_audio.track.name}")
        publication_video = await self.chatRoom.local_participant.publish_track(
            self.broadcastVideoTrack, livekit.rtc.TrackPublishOptions(source=livekit.rtc.TrackSource.SOURCE_CAMERA, red=False))
        logger.Logger.log(f"broadcast video track published: {
            publication_video.track.name}")

        self.audioBroadcastingThread = threading.Thread(
            target=self.runBroadcastingLoop, args=(audioSource,))
        self.audioBroadcastingThread.start()
        self.videoBroadcastingThread = threading.Thread(
            target=self.runVideoBroadcastingLoop, args=(videoSource,))
        self.videoBroadcastingThread.start()

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
                    if self.broadcastMissionCancelled:
                        break
                    
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
    
    
    def drawLogs(self) -> numpy.ndarray:
        img = PIL.Image.new('RGBA', (webFrontend.config.LIVEKIT_VIDEO_WIDTH, webFrontend.config.LIVEKIT_VIDEO_HEIGHT), color='black')
        draw = PIL.ImageDraw.Draw(img)
        try:
            font = PIL.ImageFont.truetype(
                'consolas.ttf', size=20)
        except IOError:
            font = PIL.ImageFont.load_default(size=20)
        for i, log in enumerate(self.connectionLogs[-48:]):
            draw.text((10, 10 + i * 20), log, font=font, fill=(255, 255, 255))
            
        if len(self.connectionLogs) > 48:
           del self.connectionLogs[:48]
        # export ndarray for image
        img_np = numpy.array(img)
        # logger.Logger.log(img_np.shape)
        return img_np
    
    
    async def broadcastVideoLoop(self, source: livekit.rtc.VideoSource):
        logger.Logger.log('broadcasting video...')
        while self.connected:
            # logger.Logger.log(self.broadcastMissions.qsize(), 'missions in queue')
            # build video frame for 64 lines of logs 
            img_np = self.drawLogs()
            # logger.Logger.log(img_np.shape, len(img_np.tobytes()))
            livekitFrame = livekit.rtc.VideoFrame(
                data=img_np.astype(numpy.uint8),
                width=webFrontend.config.LIVEKIT_VIDEO_WIDTH,
                height=webFrontend.config.LIVEKIT_VIDEO_HEIGHT,
                type=livekit.rtc.VideoBufferType.BGRA
            )
            source.capture_frame(livekitFrame)
            await asyncio.sleep(1/30)
        
        logger.Logger.log('broadcasting video stopped')
            
    

    def getUserMedia(self) -> dict[str, bytes | str]:
        """
        Get image of user's camera or sharing screen.

        Returns:
            dict[str, bytes | str]: Image file of user's camera or sharing screen.
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

        # resize the image so as to save the token
        scaler = self.currentImageFrame.width / 1280
        new_width, new_height = (int(
            self.currentImageFrame.width // scaler), int(self.currentImageFrame.height // scaler))
        cv2.resize(img_np, (new_width, new_height))

        encoded, buffer = cv2.imencode('.jpg', img_np)

        """
        temp = self.dataProvider.tempFilePathProvider('jpg')
        with open(temp, 'wb') as f:
            f.write(buffer.tobytes())
        logger.Logger.log(f"saved as {temp}")
        """

        return {
            'mime_type': 'image/jpeg',
            'data': buffer.tobytes()
        }

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
            await self.llmSession.send('EOF', end_of_turn=True)
            # do it in chat thread
            SileroVAD.SileroVAD.reset()
            logger.Logger.unregisterCallback(self.loggerCallbackId)
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
                sessionName).memory.getCharTTSUseModel() != None) else 'False')
            if TokenCounter(plain) < 621 and self.getSession(sessionName).memory.getCharTTSUseModel() != "None":
                # if True:
                # remove all emojis in `plain`
                plain = removeEmojis(plain)
                for i in self.getSession(sessionName).getAvailableStickers():
                    # fuck unicode parentheses
                    plain = plain.replace(f'（{i}）', f'({i})')
                    # I hate gemini-1.0
                    plain = plain.replace(f':{i}:', f'({i})')

                result = self.dataProvider.convertModelResponseToAudioV2(
                    self.getSession(
                        sessionName).memory.getCharTTSUseModel(),
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

                    if TokenCounter(plain) < 621 and self.getSession(sessionName).memory.getCharTTSUseModel() != "None":
                        # remove all emojis in `plain`
                        plain = removeEmojis(plain)
                        for i in self.getSession(sessionName).getAvailableStickers():
                            # fuck unicode parentheses
                            plain = plain.replace(f'（{i}）', f'({i})')
                            # I hate gemini-1.0
                            plain = plain.replace(f':{i}:', f'({i})')

                        result = self.dataProvider.convertModelResponseToAudioV2(
                            self.getSession(
                                sessionName).memory.getCharTTSUseModel(),
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
