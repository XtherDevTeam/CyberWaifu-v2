import tools
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
import typing
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
import Tha4Api

from models import EmojiToStickerInstrctionModel, TokenCounter

import emoji

import webFrontend.extensionHandler
from workflowTools import ToolResponse
import workflowTools


def removeEmojis(text: str):
    text = text.replace('🎵', '(note)')
    text = emoji.replace_emoji(text, '')
    text = text.replace('(note)', '🎵')
    return text


class VoiceChatResponse():
    """
    A class for storing voice chat response as bytes.
    """

    def __init__(self, response: requests.models.Response) -> None:
        self.response = response
        self.chunked_iter = response.iter_content(
            chunk_size=4096)  # just magic number
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


class VoiceChatResponseV2():
    """
    New version of VoiceChatResponse class that runs in a separate thread and no streamed response.
    """

    def __init__(self, url: str, text: str):
        self.url = url
        self.text = text
        self.thread = threading.Thread(target=self.run, args=())
        self.thread.start()
        self.response: Optional[requests.models.Response] = None

    def run(self) -> None:
        logger.Logger.log(self.url)
        self.response = requests.get(self.url, stream=False)

    def get(self) -> typing.Tuple[bytes, str]:
        if self.thread.is_alive():
            self.thread.join()
        logger.Logger.log(f"got response for {self.text}")
        return av.open(io.BytesIO(self.response.content)), self.text


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
        self.beginTime = time.time()
        self.bot = instance.Chatbot(memory.Memory(
            dataProvider, charName, True), dataProvider.getUserName(), rtSession=True)
        self.llmSession = None
        self.chatRoom: Optional[livekit.rtc.Room] = None
        self.dataProvider = dataProvider
        self.currentImageFrame: Optional[livekit.rtc.VideoFrame] = None
        self.broadcastAudioTrack: Optional[livekit.rtc.AudioTrack] = None
        self.broadcastMissions: queue.Queue[VoiceChatResponseV2] = queue.Queue(
        )
        self.currentBroadcastMission: Optional[av.InputContainer |
                                               av.OutputContainer] = None
        self.ttsUseModel = self.bot.memory.getCharTTSUseModel()
        self.AIDubMiddlewareAPI = AIDubMiddlewareAPI.AIDubMiddlewareAPI(
            self.dataProvider.getGPTSoVITsMiddleware())
        self.tha4Api = Tha4Api.Tha4Api(
            self.dataProvider.getTha4MiddlewareAPI())
        self.tha4ApiSessionName = ''
        self.tha4Participant = None
        self.chat_lock = threading.Lock()
        self.message_queue: list[str] = []
        self.terminateSessionCallback = None
        self.loop: asyncio.AbstractEventLoop = None
        self.audioBroadcastingThread: threading.Thread = None
        self.connected: bool = False
        self.connectionLogs: list[str] = []
        self.loggerCallbackId: None | int = None
        self.broadcastMissionCancelled: bool = False
        self.vad_buffer = bytearray()
        self.vad_sample_rate = 16000
        self.vad_frame_size = 512  # Samples for 16kHz
        self.vad_frame_bytes = self.vad_frame_size * 2  # 2 bytes per int16 sample
        logger.Logger.log('initialized voice chat session')

    async def wait_until_llm_session_ready(self):
        while self.llmSession is None:
            await asyncio.sleep(0.1)

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
            self.broadcastMissions.put(VoiceChatResponseV2(
                self.AIDubMiddlewareAPI.build_dub_request(i['text'], self.ttsUseModel), i['text']))
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

    async def chatRealtime(self):
        """
        New real time chat method for gemini-2.0-flash-exp
        """
        buffer = ''
        while True:
            def broadcastOne(text: str):
                self.broadcastMissionCancelled = False

                resp = removeEmojis(text)
                # use |<spliter>| to split setences
                for i in self.bot.getAvailableStickers():
                    # fuck unicode parentheses
                    resp = resp.replace(f'({i})', '|<spliter>|')
                    resp = resp.replace(f'（{i}）', '|<spliter>|')
                    # I hate gemini-1.0
                    resp = resp.replace(f':{i}:', '|<spliter>|')

                resp = re.sub(r'\.(?!\.)', '.|<spliter>|', resp)
                resp = resp.replace(f'?', '?|<spliter>|')
                resp = resp.replace(f'!', '!|<spliter>|')

                # capture whitespace more than 2 times in a row
                resp = re.sub(r'\s{2,}', '|<spliter>|', resp)

                logger.Logger.log(f"Chat response: {resp}")

                def new_thread():
                    self.ttsInvocation(
                        self.dataProvider.parseModelResponse(resp, isRTVC=True))

                threading.Thread(target=new_thread).start()

            async for response in self.llmSession.receive():
                # recv a turn of chat
                if response.text is not None:
                    buffer += response.text

            print(buffer)

            if not self.connected:
                logger.Logger.log(
                    'Session terminated, stopping chatRealtime loop')
                self.bot.memory.storeMemory(self.bot.userName, buffer)
                self.bot.memory.dataProvider.saveChatHistory(self.bot.memory.getCharName(), [
                    {
                        'type': dataProvider.ChatHistoryType.TEXT,
                        'text': f'Voice chat: duration {time.strftime("%H:%M:%S", time.gmtime(time.time() - self.beginTime))}',
                        'timestamp': int(time.time()),
                        'role': 'user'
                    }
                ])
                # memory stored, close the session safely
                await self.llmPreSession.__aexit__(None, None, None)
                break

            toolsResponse = self.toolsHandler.parseRawResponse(buffer)

            if 'intents' in toolsResponse and toolsResponse['intents']:
                intent_result = []
                for i in toolsResponse['intents']:
                    handle_result = self.toolsHandler.handleIntent(
                        i['name'], i['content'])
                    if handle_result is not None:
                        intent_result.append(handle_result)

                if intent_result:
                    modelInput = [r.asModelInput() if isinstance(
                        r, workflowTools.ToolResponse) else str(r) for r in intent_result]
                    await self.send_llm(input=modelInput, end_of_turn=True)

            broadcastOne(toolsResponse['response'])

            buffer = ''

    def pcmToWav(self, pcm_data: bytes) -> bytes:
        """
        Convert PCM data to WAV format.

        Args:
            pcm_data (bytes): PCM data

        Returns:
            bytes: WAV data
        """
        with io.BytesIO() as wav_buffer:
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(16000)
                wav_file.writeframes(pcm_data)
            return wav_buffer.getvalue()

    async def forwardAudioStream(self, stream: livekit.rtc.AudioStream, mimeType: str) -> None:
        """
        Forward audio stream to LLM session in the session.

        Args:
            stream (livekit.rtc.AudioStream): audio stream
            mimeType (str): mime type of the audio stream

        Returns:
            None
        """
        frames_count = 0  # Renamed to avoid confusion with AudioFrame objects
        last_sec = time.time()
        last_sec_frames = 0
        limit_to_send = 100
        data_chunk = b''  # For LLM

        # VAD specific state
        ring_frame, current_count = 0, 0

        current_stream_resampler = None

        ext = mimetypes.guess_extension(mimeType)
        logger.Logger.log('using audio extension:', ext)

        await self.wait_until_llm_session_ready()
        async for frame in stream:
            if not self.connected:
                break

            if current_stream_resampler is None:
                current_stream_resampler = livekit.rtc.AudioResampler(
                    frame.frame.sample_rate,
                    self.vad_sample_rate,  # Target 16kHz
                    num_channels=1,
                    quality=livekit.rtc.AudioResamplerQuality.VERY_HIGH
                )

            last_sec_frames += 1
            frames_count += 1

            # --- Audio Resampling and Buffering for both LLM and VAD ---
            # Resample the current frame to 16kHz
            resampled_samples = current_stream_resampler.push(frame.frame)

            if not resampled_samples:
                continue

            for resampled_audio_frame in resampled_samples:
                resampled_bytes = resampled_audio_frame.data.tobytes()

                # --- 1. Buffer for LLM ---
                data_chunk += resampled_bytes
                if frames_count % limit_to_send == 0:
                    # pathlib.Path(f"./temp/audio.{random.randint(1, 1000000)}.wav").write_bytes(self.pcmToWav(data_chunk))
                    await self.send_llm(input={"data": data_chunk, "mime_type": "audio/pcm"})
                    data_chunk = b''

                # --- 2. Buffer for VAD ---
                self.vad_buffer.extend(resampled_bytes)

                while len(self.vad_buffer) >= self.vad_frame_bytes:
                    vad_chunk_bytes = self.vad_buffer[:self.vad_frame_bytes]
                    self.vad_buffer = self.vad_buffer[self.vad_frame_bytes:]

                    # Convert to numpy array for SileroVAD
                    numpy_data = numpy.frombuffer(
                        vad_chunk_bytes, dtype=numpy.int16)

                    isSpeech = SileroVAD.SileroVAD.predict(
                        numpy_data, self.vad_sample_rate)

                    if isSpeech > 0.7:
                        ring_frame += 1

                    if ring_frame > 10:
                        logger.Logger.log(
                            'Cancelling ongoing broadcast missions')
                        self.cancelOngoingBroadcast()
                        current_count = 0
                        ring_frame = 0

                    current_count += 1
                    if current_count > 20:
                        current_count = 0
                        ring_frame = 0

            # Logging for debugging
            if time.time() - last_sec > 1:
                last_sec = time.time()
                logger.Logger.log(
                    f"forwardAudioStream: last second: {last_sec_frames} frames, "
                    f"input_channels: {frame.frame.num_channels}, input_sample_rate: {frame.frame.sample_rate}, "
                    f"VAD_buffer_len: {len(self.vad_buffer)}, limit_to_send: {limit_to_send}")
                last_sec_frames = 0

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
        await self.wait_until_llm_session_ready()
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

            await self.send_llm(input={"data": buffer.tobytes(), "mime_type": "image/jpeg"})

    async def send_llm(self, input, end_of_turn=False):
        await self.llmSession.send(input=input, end_of_turn=end_of_turn)

    async def start(self, botToken: str, live2d_token: str, loop: asyncio.AbstractEventLoop) -> None:
        """
        Start the hoster of chat session.

        Returns:
            None
        """

        logger.Logger.log('Preparing to start chat...')
        self.loop = loop
        self.chatRoom = livekit.rtc.Room(loop)
        self.connected = True
        self.loggerCallbackId = logger.Logger.registerCallback(
            lambda s: self.connectionLogs.append(s))
        logger.Logger.log('Establishing connection to THA4 API...')
        self.live2d_token = live2d_token
        self.tha4_service = self.dataProvider.getCharacterTHA4Service(
            self.charName)
        self.tha4ApiSessionName = self.tha4Api.establish_session(
            self.tha4_service['configuration'], self.tha4_service['avatar'], 30, self.live2d_token, f'wss://{webFrontend.config.LIVEKIT_API_EXTERNAL_URL}')
        logger.Logger.log(
            f"THA4 API session established: {self.tha4ApiSessionName}")

        # patch for google.genai
        if os.getenv("ALL_PROXY") is not None:
            logger.Logger.log(
                "ALL_PROXY environment variable detected, patching google.genai.live.connect")
            proxy = websockets_proxy.Proxy.from_url(os.getenv("ALL_PROXY"))

            def fake_connect(*args, **kwargs):
                return websockets_proxy.proxy_connect(*args, proxy=proxy, **kwargs)
            google.genai.live.connect = fake_connect

        self.toolsHandler = webFrontend.extensionHandler.ToolsHandler(
            None, self.dataProvider, workflowTools.AvailableTools(), self.dataProvider.getAllEnabledUserScripts())
        client = google.genai.Client(http_options={'api_version': 'v1alpha'})
        model_id = "gemini-2.5-flash-live-preview"
        gemini_config = {"response_modalities": ["TEXT"], "system_instruction": models.PreprocessPrompt(self.bot.memory.createCharPromptFromCharacter(
            self.bot.userName), {
            'generated_tool_descriptions': self.toolsHandler.generated_tool_descriptions,
            'extra_info': self.toolsHandler.generated_extra_infos
        }), "temperature": 0.9}
        self.llmPreSession = client.aio.live.connect(
            model=model_id, config=gemini_config)
        self.llmSession = await self.llmPreSession.__aenter__()
        logger.Logger.log(f"LLM session established: {self.llmSession}")
        print("Default's", id(asyncio.get_event_loop()))

        @self.chatRoom.on("track_subscribed")
        def on_track_subscribed(track: livekit.rtc.Track, publication: livekit.rtc.RemoteTrackPublication, participant: livekit.rtc.RemoteParticipant):
            logger.Logger.log(f"track subscribed: {publication.sid}")
            if participant.identity == 'live2d':
                logger.Logger.log('Live2D track detected, ignoring...')
                pass
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
            self.terminateSession()

        @self.chatRoom.on("connected")
        def on_connected() -> None:
            logger.Logger.log("connected")

        logger.Logger.log(
            f'connecting to room wss://{webFrontend.config.LIVEKIT_API_EXTERNAL_URL} with {botToken} ...')
        await self.chatRoom.connect(f"wss://{webFrontend.config.LIVEKIT_API_EXTERNAL_URL}", botToken)

        # publish track
        # audio
        audioSource = livekit.rtc.AudioSource(
            webFrontend.config.LIVEKIT_SAMPLE_RATE, 1)
        self.broadcastAudioTrack = livekit.rtc.LocalAudioTrack.create_audio_track(
            "stream_track", audioSource)
        # video
        # videoSource = livekit.rtc.VideoSource(
        #     webFrontend.config.LIVEKIT_VIDEO_WIDTH, webFrontend.config.LIVEKIT_VIDEO_HEIGHT)
        # self.broadcastVideoTrack = livekit.rtc.LocalVideoTrack.create_video_track(
        #     "video_track", videoSource)
        # # we don't support audio/red format
        publication_audio = await self.chatRoom.local_participant.publish_track(
            self.broadcastAudioTrack, livekit.rtc.TrackPublishOptions(source=livekit.rtc.TrackSource.SOURCE_MICROPHONE, red=False))
        logger.Logger.log(f"broadcast audio track published: {
            publication_audio.track.name}")
        # publication_video = await self.chatRoom.local_participant.publish_track(
        #     self.broadcastVideoTrack, livekit.rtc.TrackPublishOptions(source=livekit.rtc.TrackSource.SOURCE_SCREENSHARE, red=False))
        # logger.Logger.log(f"broadcast video track published: {
        #     publication_video.track.name}")
        asyncio.ensure_future(self.chatRealtime())
        asyncio.ensure_future(self.broadcastAudioLoop(audioSource))
        # asyncio.ensure_future(self.broadcastVideoLoop(videoSource))
        # self.audioBroadcastingThread = threading.Thread(
        #     target=self.runBroadcastingLoop, args=(audioSource,))
        # self.audioBroadcastingThread.start()
        # self.videoBroadcastingThread = threading.Thread(
        #     target=self.runVideoBroadcastingLoop, args=(videoSource,))
        # self.videoBroadcastingThread.start()

        # self.runVideoBroadcastingLoop(videoSource)

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
            self.currentBroadcastMission, self.currentBroadcastText = self.broadcastMissions.get().get()

        return self.currentBroadcastMission

    async def broadcastAudioLoop(self, source: livekit.rtc.AudioSource, frequency: int = 1000):
        logger.Logger.log('broadcasting audio...')
        while self.connected:
            if self.fetchBroadcastMission() is None:
                # logger.Logger.log('capturing empty audio frame...')
                await source.capture_frame(self.generateEmptyAudioFrame())
                # logger.Logger.log('done2')
            else:
                logger.Logger.log('broadcasting mission...')
                sentiment = self.AIDubMiddlewareAPI.sentiment(
                    self.currentBroadcastText)['sentiment']
                self.tha4Api.switch_state(self.tha4ApiSessionName, sentiment)
                logger.Logger.log(
                    f"Sentiment: {sentiment}, emitted switch_state signal.")
                frame: Optional[av.AudioFrame] = None
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

        logger.Logger.log('broadcasting audio stopped')

    def drawLogs(self) -> numpy.ndarray:
        img = PIL.Image.new('RGBA', (webFrontend.config.LIVEKIT_VIDEO_WIDTH,
                            webFrontend.config.LIVEKIT_VIDEO_HEIGHT), color='black')
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
            await self.send_llm('EOF', end_of_turn=True)
            # do it in chat thread
            SileroVAD.SileroVAD.reset()
            logger.Logger.unregisterCallback(self.loggerCallbackId)
            await self.chatRoom.disconnect()
            self.tha4Api.shutdown_session(self.tha4ApiSessionName)

        asyncio.ensure_future(f())


class ChatroomSession:
    def __init__(self, sessionName: str, charName: str, dProvider: dataProvider.DataProvider):
        self.dataProvider = dProvider
        self.charName = charName
        self.chatbot = instance.Chatbot(
            memory.Memory(
                self.dataProvider, charName),
            self.dataProvider.getUserName(),
            enabled_extra_infos=self.dataProvider.getAllEnabledExtraInfos(),
            enabled_user_scripts=self.dataProvider.getAllEnabledUserScripts()
        )
        self.expireTime = time.time() + 60 * 5
        self.available_events = {
            'message': [],
        }

        def tools_handler_intermediate_response(response: str) -> None:
            logger.Logger.log('Triggering intermediate response callback')
            logger.Logger.log(f'{response}')
            result = self.dataProvider.parseModelResponse(response)

            self.dataProvider.saveChatHistory(self.charName, result)
            self.trigger('message', result)

        self.chatbot.toolsHandler.on(
            'intermediate_response', tools_handler_intermediate_response)

    def terminate(self):
        self.chatbot.terminateChat()

    def on(self, event: str, callback: typing.Callable[..., None]) -> None:
        if event in self.available_events:
            self.available_events[event].append(callback)
        else:
            raise exceptions.EventNotFound(f"Event {event} not found")

    def trigger(self, event: str, *args, **kwargs) -> None:
        if event in self.available_events:
            for callback in self.available_events[event]:
                callback(*args, **kwargs)
        else:
            raise exceptions.EventNotFound(f"Event {event} not found")

    def beginChat(self, msgChain: list[str]):
        f = self.dataProvider.parseMessageChain(msgChain)

        self.trigger('message', f)
        plain = self.chatbot.begin(
            self.dataProvider.convertMessageHistoryToModelInput(f))
        self.dataProvider.saveChatHistory(self.charName, f)

        result = []

        logger.Logger.log('TTS available: ', 'True' if (TokenCounter(
            plain) < 621 and self.chatbot.memory.getCharTTSUseModel() != None) else 'False')
        if TokenCounter(plain) < 621 and self.chatbot.memory.getCharTTSUseModel() != "None" and random.randint(1, 5) == 1:
            # if True:
            # remove all emojis in `plain`
            plain = removeEmojis(plain)
            for i in self.chatbot.getAvailableStickers():
                plain = plain.replace(f'（{i}）', f"({i})")
                plain = plain.replace(f':{i}:', f":{i}:")
            
            for content in self.dataProvider.convertModelResponseToAudioV2(
                self.chatbot.memory.getCharTTSUseModel(), self.dataProvider.parseModelResponse(plain)):
                self.dataProvider.saveChatHistory(self.charName, [content])
                self.trigger('message', [content])

        else:
            plain = EmojiToStickerInstrctionModel(plain, ''.join(
                f'({i}) ' for i in self.chatbot.getAvailableStickers()))
            plain = removeEmojis(plain)
            for i in self.chatbot.getAvailableStickers():
                plain = plain.replace(f'（{i}）', f"({i})")
                plain = plain.replace(f':{i}:', f":{i}:")

            result = self.dataProvider.parseModelResponse(plain)
            self.dataProvider.saveChatHistory(self.charName, result)
            self.trigger('message', result)


    def sendMessage(self, msgChain: list[str]) -> None:
        f = self.dataProvider.parseMessageChain(msgChain)

        self.trigger('message', f)
        self.dataProvider.saveChatHistory(self.charName, f)

        result = None
        retries = 0
        while result == None:
            plain = tools.retryWrapper(lambda: self.chatbot.chat(
                userInput=self.dataProvider.convertMessageHistoryToModelInput(f)))
            if TokenCounter(plain) < 621 and self.chatbot.memory.getCharTTSUseModel() != "None" and random.randint(1, 5) == 1:
                # if True:
                for i in self.chatbot.getAvailableStickers():
                    plain = plain.replace(f'（{i}）', f"({i})")
                    plain = plain.replace(f':{i}:', f":{i}:")

                for content in self.dataProvider.convertModelResponseToAudioV2(
                    self.chatbot.memory.getCharTTSUseModel(), self.dataProvider.parseModelResponse(plain)):
                    self.dataProvider.saveChatHistory(self.charName, [content])
                    self.trigger('message', [content])
                    
            else:
                plain = tools.retryWrapper(lambda: EmojiToStickerInstrctionModel(plain, ''.join(
                    f'({i}) ' for i in self.chatbot.getAvailableStickers())))
                plain = removeEmojis(plain)
                for i in self.chatbot.getAvailableStickers():
                    plain = plain.replace(f'（{i}）', f"({i})")
                    plain = plain.replace(f':{i}:', f":{i}:")

                result = self.dataProvider.parseModelResponse(plain)

                self.dataProvider.saveChatHistory(self.charName, result)
                self.trigger('message', result)


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

        self.available_events = {
            'message': [],
        }

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
        session = ChatroomSession(sessionName, charName, self.dataProvider)
        session.on('message', lambda x: self.trigger(
            'message', sessionName, x))

        self.pool[sessionName] = {
            'expireTime': time.time() + 60 * 5,
            'session': session,
            'history': [],
            'charName': charName,
            'client': None
        }

        return sessionName

    def on(self, event: str, callback: typing.Callable[..., None]) -> None:
        if event in self.available_events:
            self.available_events[event].append(callback)
        else:
            raise exceptions.EventNotFound(f"Event {event} not found")

    def trigger(self, event: str, *args, **kwargs) -> None:
        if event in self.available_events:
            for callback in self.available_events[event]:
                callback(*args, **kwargs)
        else:
            raise exceptions.EventNotFound(f"Event {event} not found")

    def bindClient(self, sessionName: str, client: str) -> None:
        if sessionName in self.pool:
            self.pool[sessionName]['client'] = client
            logger.Logger.log(
                f'Bound client {client} to session {sessionName}')
        else:
            raise exceptions.SessionNotFound(
                f'{__name__}: Session {sessionName} not found or expired')

    def getSessionByClient(self, client: str) -> ChatroomSession:
        for i in self.pool.keys():
            if self.pool[i]['client'] == client:
                return self.pool[i]['session']
        return None

    def getClientBySession(self, sessionName: str) -> str:
        if sessionName in self.pool:
            return self.pool[sessionName]['client']
        else:
            raise exceptions.SessionNotFound(
                f'{__name__}: Session {sessionName} not found or expired')

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

    def getSession(self, sessionName: str, doRenew: bool = True) -> ChatroomSession:
        if sessionName in self.pool:
            r: ChatroomSession = self.pool[sessionName]['session']
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

    def beginChat(self, sessionName: str, msgChain: list[str]):
        if sessionName in self.pool:
            session = self.getSession(sessionName)
            session.beginChat(msgChain)
        else:
            raise exceptions.SessionNotFound(
                f'{__name__}: Session {sessionName} not found or expired')

    def sendMessage(self, sessionName: str, msgChain: list[str]):
        if sessionName in self.pool:
            session = self.getSession(sessionName)
            session.sendMessage(msgChain)
        else:
            raise exceptions.SessionNotFound(
                f'{__name__}: Session {sessionName} not found or expired')

    def terminateSession(self, sessionName: str) -> None:
        if sessionName in self.pool:
            self.getSession(sessionName, False).terminate()
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
