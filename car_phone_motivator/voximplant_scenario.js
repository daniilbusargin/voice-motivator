/**
 * Voximplant VoxEngine scenario — Car Phone Motivator
 *
 * Flow:
 *  1. Incoming call is answered.
 *  2. POST /call/webhook {event: "call_started"} → get greeting audio_url.
 *  3. Play greeting to caller.
 *  4. Record caller's reply (max RECORD_SECONDS, stop on silence).
 *  5. POST /call/audio with the recorded file URL.
 *  6. Play the returned answer audio.
 *  7. Repeat from step 4 until call ends.
 *
 * Configure in Voximplant Dashboard:
 *   - Set BACKEND_URL to your public FastAPI URL (no trailing slash).
 *   - Attach this scenario to an Application → Rule for the phone number.
 */

var BACKEND_URL = "https://your-backend.example.com"; // <-- change this
var RECORD_SECONDS = 8;         // max seconds to record per turn
var SILENCE_THRESHOLD = 1500;   // ms of silence before stopping record
var MAX_TURNS = 20;             // safety limit

var call = null;
var callId = null;
var turn = 0;

VoxEngine.addEventListener(AppEvents.CallAlerting, function (e) {
    call = e.call;
    callId = call.id();
    Logger.write("[motivator] CallAlerting id=" + callId);

    call.addEventListener(CallEvents.Connected, onCallConnected);
    call.addEventListener(CallEvents.Disconnected, onCallDisconnected);
    call.addEventListener(CallEvents.Failed, onCallFailed);

    call.answer();
});

function onCallConnected() {
    Logger.write("[motivator] Connected id=" + callId);
    notifyBackend("call_started", null, function (greetingUrl) {
        if (greetingUrl) {
            playAndRecord(greetingUrl);
        } else {
            recordCaller(); // skip greeting if backend returned nothing
        }
    });
}

function notifyBackend(event, audioUrl, cb) {
    var body = JSON.stringify({ event: event, call_id: callId, audio_url: audioUrl });
    Net.httpRequest(BACKEND_URL + "/call/webhook", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        postData: body,
        async: true,
        success: function (resp) {
            try {
                var data = JSON.parse(resp.text);
                cb(data.audio_url || null);
            } catch (ex) {
                Logger.write("[motivator] parse error: " + ex);
                cb(null);
            }
        },
        error: function (err) {
            Logger.write("[motivator] webhook error: " + err);
            cb(null);
        }
    });
}

function playAndRecord(audioUrl) {
    var player = VoxEngine.createURLPlayer(audioUrl);
    player.addEventListener(PlayerEvents.PlaybackFinished, function () {
        recordCaller();
    });
    call.startMediaStream(player);
    player.play();
}

function recordCaller() {
    if (turn >= MAX_TURNS) {
        Logger.write("[motivator] max turns reached, ending call");
        call.hangup();
        return;
    }
    turn++;
    Logger.write("[motivator] recording turn=" + turn);

    var recorder = VoxEngine.createRecorder({
        maxDuration: RECORD_SECONDS * 1000,
        silenceTimeout: SILENCE_THRESHOLD,
    });

    recorder.addEventListener(RecorderEvents.Stopped, function (e) {
        var recordUrl = e.url; // Voximplant stores the recording and gives a URL
        Logger.write("[motivator] recorded url=" + recordUrl);
        sendAudioToBackend(recordUrl);
    });

    call.startMediaStream(recorder);
}

function sendAudioToBackend(recordUrl) {
    var body = JSON.stringify({
        call_id: callId,
        audio_url: recordUrl,
        audio_format: "oggopus"
    });
    Net.httpRequest(BACKEND_URL + "/call/audio", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        postData: body,
        async: true,
        success: function (resp) {
            try {
                var data = JSON.parse(resp.text);
                Logger.write("[motivator] answer=" + data.answer_text);
                if (data.audio_url) {
                    playAndRecord(data.audio_url);
                } else {
                    recordCaller(); // empty input, listen again
                }
            } catch (ex) {
                Logger.write("[motivator] parse error: " + ex);
                recordCaller();
            }
        },
        error: function (err) {
            Logger.write("[motivator] audio endpoint error: " + err);
            recordCaller();
        }
    });
}

function onCallDisconnected() {
    Logger.write("[motivator] Disconnected id=" + callId);
    notifyBackend("call_ended", null, function () {});
    VoxEngine.terminate();
}

function onCallFailed(e) {
    Logger.write("[motivator] Failed code=" + e.code + " id=" + callId);
    VoxEngine.terminate();
}
