start_web_backend:
	python app.py -s

start_livekit:
	livekit-server --config=blob/livekit.yml
