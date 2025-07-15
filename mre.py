import livekit
import livekit.api
import livekit.rtc
import google.genai
import google.genai.live
import asyncio
import numpy
import cv2
import base64
import av
import time
import json
import os
import websockets_proxy

new_loop = asyncio.new_event_loop()
asyncio.set_event_loop(new_loop)

async def getLiveKitAPI():
    return livekit.api.LiveKitAPI(f"https://www.xiaokang00010.top:6212", "YoimiyaGaTaisukiDesu06210621062106210621", "YoimiyaGaTaisukiDesu06210621062106210621")

userToken = livekit.api.AccessToken(
        "YoimiyaGaTaisukiDesu06210621062106210621", "YoimiyaGaTaisukiDesu06210621062106210621").with_identity(
        'user').with_name("Jerry Chou").with_grants(livekit.api.VideoGrants(room_join=True, room="testroom")).to_jwt()

botToken = livekit.api.AccessToken(
        "YoimiyaGaTaisukiDesu06210621062106210621", "YoimiyaGaTaisukiDesu06210621062106210621").with_identity(
        'model').with_name("Awwa").with_grants(livekit.api.VideoGrants(room_join=True, room="testroom")).to_jwt()

    # livekit api is in this file, so we can't put this logic into createRtSession
async def f():
    await (await getLiveKitAPI()).room.create_room(create=livekit.api.CreateRoomRequest(name="testroom", empty_timeout=10*60, max_participants=2))

asyncio.get_event_loop().run_until_complete(f())

print("User token: ", userToken)
print("Bot token: ", botToken)

class MRE:
    def __init__(self, name = "Gemini"):
        self.name = name
        
    
    async def chatRealtime(self):
        buffer = ''
        while True:
            async for response in self.llmSession.receive():
                if response.text is None:
                    # a turn is finished
                    break
                print(f"Recved {len(response.text)}")
                buffer += response.text
            print("End of turn ", buffer, self.llmSession._ws.close_code, self.llmSession._ws.close_reason)
            buffer = ''
    
        
    async def start(self, loop = new_loop):
        if os.getenv("HTTP_PROXY"):
            proxy = websockets_proxy.Proxy.from_url(os.getenv("HTTP_PROXY"))
            def fake_connect(*args, **kwargs):
                return websockets_proxy.proxy_connect(*args, proxy=proxy, **kwargs)
            google.genai.live.connect = fake_connect
            
        print("Preparing for launch...")
        client = google.genai.Client(http_options={'api_version': 'v1alpha'})
        model_id = "gemini-2.0-flash-exp"
        config = {"response_modalities": ["TEXT"]}
        self.llmPreSession = client.aio.live.connect(model=model_id, config=config)
        self.llmSession: google.genai.live.AsyncSession = await self.llmPreSession.__aenter__()
        self.chatRoom = livekit.rtc.Room(loop)
        
        asyncio.ensure_future(self.chatRealtime())
        
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
                    self.forwardAudioStream(livekit.rtc.AudioStream(track), publication.mime_type))
                
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

            self.terminateSession()

        @self.chatRoom.on("connected")
        def on_connected() -> None:
            print("connected")
                
        
        print("Connecting to LiveKit...")
        await self.chatRoom.connect(f"wss://www.xiaokang00010.top:6212", botToken)
        print("Connected to LiveKit.")
        # publish track
        # audio
        # audioSource = livekit.rtc.AudioSource(
        #     48000, 1)
        # self.broadcastAudioTrack = livekit.rtc.LocalAudioTrack.create_audio_track(
        #     "stream_track", audioSource)
        # publication_audio = await self.chatRoom.local_participant.publish_track(
        #     self.broadcastAudioTrack, livekit.rtc.TrackPublishOptions(source=livekit.rtc.TrackSource.SOURCE_MICROPHONE, red=False))
        # import threading
        # self.audioBroadcastingThread = threading.Thread(
        #     target=self.runBroadcastingLoop, args=(audioSource,))
        # self.audioBroadcastingThread.start()
        
        video_source = livekit.rtc.VideoSource(640, 480)
        self.broadcastVideoTrack = livekit.rtc.LocalVideoTrack.create_video_track(
            "stream_track", video_source)
        publication_video = await self.chatRoom.local_participant.publish_track(
            self.broadcastVideoTrack, livekit.rtc.TrackPublishOptions(source=livekit.rtc.TrackSource.SOURCE_CAMERA, red=False))
        print("Published video track.")
                
        print("Waiting for participants to join...")
        while True:
            if self.llmSession:
                print("Test", self.llmSession._ws.close_code, self.llmSession._ws.close_reason)
            await asyncio.sleep(1)


    def runBroadcastingLoop(self, audioSource) -> None:
        """
        Start the loop for broadcasting missions.

        Returns:
            None
        """
        print('starting broadcasting loop')
        new_loop = asyncio.new_event_loop()
        new_loop.run_until_complete(self.broadcastAudioLoop(audioSource))


    def generateEmptyAudioFrame(self) -> livekit.rtc.AudioFrame:
        """
        Generate an empty audio frame.

        Returns:
            livekit.rtc.AudioFrame: empty audio frame
        """
        amplitude = 32767  # for 16-bit audio
        samples_per_channel = 480  # 10ms at 48kHz
        time = numpy.arange(samples_per_channel) / \
            48000
        total_samples = 0
        audio_frame = livekit.rtc.AudioFrame.create(
            48000, 1, samples_per_channel)
        audio_data = numpy.frombuffer(audio_frame.data, dtype=numpy.int16)
        time = (total_samples + numpy.arange(samples_per_channel)) / \
            48000
        wave = numpy.int16(0)
        numpy.copyto(audio_data, wave)
        # logger.Logger.log('done1')
        return audio_frame

        
    async def receiveVideoStream(self, stream: livekit.rtc.VideoStream):
        async for frame in stream:
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
            
            await self.llmSession.send(input={"data": buffer.tobytes(), "mime_type": "image/jpeg"})
            
        
    async def forwardAudioStream(self, stream: livekit.rtc.AudioStream, mime_type: str):
        frames = 0
        last_sec = time.time()
        last_sec_frames = 0
        limit_to_send = 100
        data_chunk = b''
        def resample(livekitFrame, inputRate) -> livekit.rtc.AudioFrame:
            resampler = livekit.rtc.AudioResampler(input_rate=inputRate, output_rate=16000, num_channels=1, quality=livekit.rtc.AudioResamplerQuality.HIGH)
            resampler.push(livekitFrame)
            return resampler.flush()[0]
        async for frame in stream:
            last_sec_frames += 1
            frames += 1
            avFrame = av.AudioFrame.from_ndarray(numpy.frombuffer(resample(frame.frame, frame.frame.sample_rate).data, dtype=numpy.int16).reshape(frame.frame.num_channels, -1), layout='mono', format='s16')
            data_chunk += avFrame.to_ndarray().tobytes()
            if frames % limit_to_send == 0:
                await self.llmSession.send(input={"data": data_chunk, "mime_type": "audio/pcm"})
            
                data_chunk = b''
                    
            if time.time() - last_sec > 1:
                last_sec = time.time()
                print(f"forwardAudioStream: last second: {last_sec_frames} frames, num_channels: {frame.frame.num_channels}, sample_rate: {frame.frame.sample_rate}, limit_to_send: {limit_to_send}")
                last_sec_frames = 0
                
                
    async def broadcastAudioLoop(self, source: livekit.rtc.AudioSource, frequency: int = 1000):
        print('broadcasting audio...')
        
        while True:
            await source.capture_frame(self.generateEmptyAudioFrame())
            
    
mre = MRE()

asyncio.ensure_future(mre.start(new_loop))

new_loop.run_forever()