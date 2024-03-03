import models
import instance
import flask
from flask_cors import CORS, cross_origin
import time
import webFrontend.chatbotManager as chatbotManager
import dataProvider
import config
import webFrontend.config
from io import BytesIO

app = flask.Flask(__name__)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
app.config['SECRET_KEY'] = webFrontend.config.SECRET_KEY
dProvider = dataProvider.DataProvider(f'{config.BLOB_URL}/data.db')
chatbotManager = chatbotManager.chatbotManager(dProvider)

def parseRequestRange(s, flen):
    s = s[s.find('=')+1:]
    c = s.split('-')
    if len(c) != 2:
        return None
    else:
        if c[0] == '' and c[1] == '':
            return [0, flen - 1]
        elif c[1] == '':
            return [int(c[0]), flen - 1]
        elif c[0] == '':
            return [flen - int(c[1]) - 1, flen - 1]
        else:
            return [int(i) for i in c]


def makeFileResponse(file: bytes, mime: str):
    isPreview = not mime.startswith('application')
    if flask.request.headers.get('Range') != None:
        fileLength = len(file)

        reqRange = parseRequestRange(
            flask.request.headers.get('Range'), fileLength)

        response_file = bytes()

        response_file = file[reqRange[0]:reqRange[1]]

        response = flask.make_response(response_file)
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Content-Range'] = 'bytes ' + \
            str(reqRange[0]) + '-' + \
            str(reqRange[1]) + '/' + str(fileLength)
        response.headers['Content-Type'] = mime
        if response.headers['Content-Type'].startswith('application'):
            response.headers['Content-Disposition'] = "attachment;"

        response.status_code = 206
        return response
    return flask.send_file(BytesIO(file), as_attachment=not isPreview, mimetype=mime)


def authenticateSession() -> int:
    try:
        return flask.session['user']
    except:
        return -1


@app.after_request
def afterRequst(f):
    dProvider.db.db.commit()
    return f


@app.route("/api/v1/service/info", methods=["GET"])
def serviceInfo():
    return {
        'data': {
            'initialized': dProvider.checkIfInitialized(),
            'api_ver': 'v1',
            'api_name': 'Yoimiya',
            'image_model': config.USE_MODEL_IMAGE_PARSING,
            'chat_model': config.USE_MODEL,
            'authenticated_session': authenticateSession()
        },
        'status': True
    }


@app.route("/api/v1/user/login", methods=["POST"])
def userLogin():
    pwd = ''

    try:
        data = flask.request.get_json()
        pwd = data['password']
    except Exception as e:
        return {'data': 'invalid form', 'status': False}

    if dProvider.authenticate(pwd):
        flask.session['user'] = int(time.time())
        return {'data': 'success', 'status': True}
    else:
        return {'data': 'invalid password', 'status': False}


@app.route("/api/v1/char_list", methods=["POST"])
def charList():
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    return {'data': dProvider.getCharacterList(), 'status': True}


@app.route("/api/v1/chat/establish", methods=["POST"])
def chatEstablish():
    charName = ''
    beginMsg = ''

    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}
    try:
        data = flask.request.get_json()
        charName = data['charName']
        beginMsg = data['msgChain']
    except:
        return {'data': 'invalid form', 'status': False}

    session = chatbotManager.createSession(charName)
    return {'response': chatbotManager.beginChat(session, beginMsg),
            'session': session,
            'status': True}


@app.route("/api/v1/chat/message", methods=["POST"])
def chatMessage():
    session = ''
    msgChain = []

    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}
    try:
        data = flask.request.get_json()
        session = data['session']
        msgChain = data['msgChain']
    except:
        return {'data': 'invalid form', 'status': False}

    return {'response': chatbotManager.sendMessage(session, msgChain),
            'session': session,
            'status': True}


@app.route("/api/v1/chat/terminate", methods=["POST"])
def chatTerminate():
    session = ''

    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}
    try:
        data = flask.request.get_json()
        session = data['session']
    except:
        return {'data': 'invalid form', 'status': False}

    chatbotManager.terminateSession(session)

    return {'data': 'success', 'status': True}


@app.route("/api/v1/attachment/upload/audio", methods=["POST"])
def attachmentUploadAudio():
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    for i in flask.request.files:
        mime = flask.request.files[i].mimetype
        if not mime.startswith('audio/'):
            return {'data': 'invalid mimetype expect `audio/`', 'status': False}
        i = BytesIO()
        flask.request.files[i].save(i)
        i.seek(0)
        id = dProvider.saveAudioAttachment(i.read(), mime)
        # only accept the first file
        return {'data': 'success', 'id': id, 'status': True}


@app.route("/api/v1/attachment/upload/image", methods=["POST"])
def attachmentUploadImage():
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    for i in flask.request.files:
        mime = flask.request.files[i].mimetype
        if not mime.startswith('image/'):
            return {'data': 'invalid mimetype expect `image/`', 'status': False}

        i = BytesIO()
        flask.request.files[i].save(i)
        i.seek(0)
        id = dProvider.saveAudioAttachment(i.read(), mime)
        # only accept the first file
        return {'data': 'success', 'id': id, 'status': True}


@app.route("/api/v1/attachment/<attachmentId>", methods=["GET"])
def attachmentDownload(attachmentId: str):
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    mime, file = dProvider.getAttachment(attachmentId)
    return makeFileResponse(file, mime)


@app.route("/api/v1/char/<id>/avatar", methods=["GET"])
def charAvatar(id):
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    mime, file = dProvider.getCharacterAvatar(id)
    return makeFileResponse(file, mime)


@app.route("/api/v1/char/new", methods=["POST"])
def charNew():
    # offset default to 0
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    charName = ''
    charPrompt = ''
    pastMemories = ''
    exampleChats = ''

    try:
        data = flask.request.get_json()
        charName = data['charName']
        charPrompt = data['charPrompt']
        pastMemories = data['pastMemories']
        exampleChats = data['exampleChats']
    except:
        return {'data': 'invalid form', 'status': False}

    dProvider.createCharacter(charName, charPrompt, pastMemories, exampleChats)

    return {
        'data': 'success',
        'status': 'true'
    }


@app.route("/api/v1/char/<id>/history/<offset>", methods=["POST"])
def charHistory(id, offset):
    # offset default to 0
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    return {
        'data': dProvider.fetchChatHistory(id, offset),
        'status': 'true'
    }


@app.route("/api/v1/initialize", methods=["POST"])
def initialize():
    if dProvider.checkIfInitialized():
        return {'data': 'already initialized', 'status': False}

    userName = ''
    password = ''
    try:
        data = flask.request.get_json()
        userName = data['userName']
        password = data['password']
    except:
        return {'data': 'invalid form', 'status': False}

    dProvider.initialize(userName, password)
    flask.session['user'] = int(time.time())
    return {'data': 'success', 'status': True}


def invoke():
    app.run(webFrontend.config.APP_HOST,
            webFrontend.config.APP_PORT, debug=False)
