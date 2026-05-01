/**
 * Voximplant VoxEngine scenario — Car Phone Motivator
 *
 * Загрузить в: Voximplant Dashboard → Applications → <app> → Scenarios
 * Привязать к: Applications → <app> → Routing → Rules → pattern .*
 *
 * Flow:
 *  1. Входящий звонок → VoxEngine отвечает.
 *  2. POST /call/webhook {event: "call_started"} → получаем URL приветствия.
 *  3. Проигрываем приветствие водителю.
 *  4. Записываем реплику (до RECORD_SECONDS секунд или до тишины).
 *  5. POST /call/audio {call_id, audio_url} → STT + LLM + TTS на backend.
 *  6. Проигрываем ответное аудио.
 *  7. Повторяем с шага 4.
 */

// ─── Настройки ───────────────────────────────────────────────────────────────
var BACKEND_URL      = "https://your-backend.example.com"; // ← заменить на реальный URL
var RECORD_SECONDS   = 10;    // максимальная длина записи реплики
var SILENCE_MS       = 2000;  // мс тишины для автостопа записи
var MAX_TURNS        = 30;    // защита от бесконечного цикла
// ─────────────────────────────────────────────────────────────────────────────

var call    = null;
var callId  = null;
var turn    = 0;

VoxEngine.addEventListener(AppEvents.CallAlerting, function (e) {
    call   = e.call;
    callId = call.id();
    Logger.write("[motivator] CallAlerting id=" + callId);

    call.addEventListener(CallEvents.Connected,    onConnected);
    call.addEventListener(CallEvents.Disconnected, onDisconnected);
    call.addEventListener(CallEvents.Failed,       onFailed);

    call.answer();
});

// ─── Звонок принят ───────────────────────────────────────────────────────────
function onConnected() {
    Logger.write("[motivator] Connected id=" + callId);
    webhookPost({ event: "call_started", call_id: callId }, function (data) {
        if (data && data.audio_url) {
            playThenRecord(data.audio_url);
        } else {
            recordCaller(); // приветствие не пришло — сразу слушаем
        }
    });
}

// ─── Проиграть аудио, затем записать реплику ─────────────────────────────────
function playThenRecord(audioUrl) {
    var player = VoxEngine.createURLPlayer(audioUrl);
    player.addEventListener(PlayerEvents.PlaybackFinished, function () {
        recordCaller();
    });
    player.addEventListener(PlayerEvents.PlaybackFailed, function () {
        Logger.write("[motivator] Playback failed, continuing to record");
        recordCaller();
    });
    call.startMediaStream(player);
    player.play();
}

// ─── Запись реплики водителя ──────────────────────────────────────────────────
function recordCaller() {
    if (turn >= MAX_TURNS) {
        Logger.write("[motivator] Max turns reached, hanging up");
        call.hangup();
        return;
    }
    turn++;
    Logger.write("[motivator] Recording turn=" + turn);

    var recorder = VoxEngine.createRecorder({
        maxDuration:    RECORD_SECONDS * 1000,
        silenceTimeout: SILENCE_MS,
    });

    recorder.addEventListener(RecorderEvents.Stopped, function (e) {
        Logger.write("[motivator] Recorded url=" + e.url);
        sendAudio(e.url);
    });

    call.startMediaStream(recorder);
}

// ─── Отправить аудио на backend ───────────────────────────────────────────────
function sendAudio(recordUrl) {
    var body = JSON.stringify({
        call_id:      callId,
        audio_url:    recordUrl,
        audio_format: "oggopus",
    });

    Net.httpRequest(BACKEND_URL + "/call/audio", {
        method:   "POST",
        headers:  { "Content-Type": "application/json" },
        postData: body,
        async:    true,
        success: function (resp) {
            try {
                var data = JSON.parse(resp.text);
                Logger.write("[motivator] Answer: " + data.answer_text);
                if (data.audio_url) {
                    playThenRecord(data.audio_url);
                } else {
                    // пустая реплика — молча слушаем снова
                    recordCaller();
                }
            } catch (ex) {
                Logger.write("[motivator] Parse error: " + ex);
                recordCaller();
            }
        },
        error: function (err) {
            Logger.write("[motivator] HTTP error: " + err);
            recordCaller();
        },
    });
}

// ─── Вспомогательная функция POST на /call/webhook ───────────────────────────
function webhookPost(payload, cb) {
    Net.httpRequest(BACKEND_URL + "/call/webhook", {
        method:   "POST",
        headers:  { "Content-Type": "application/json" },
        postData: JSON.stringify(payload),
        async:    true,
        success: function (resp) {
            try { cb(JSON.parse(resp.text)); } catch (ex) { cb(null); }
        },
        error: function () { cb(null); },
    });
}

// ─── Конец звонка ────────────────────────────────────────────────────────────
function onDisconnected() {
    Logger.write("[motivator] Disconnected id=" + callId);
    webhookPost({ event: "call_ended", call_id: callId }, function () {});
    VoxEngine.terminate();
}

function onFailed(e) {
    Logger.write("[motivator] Failed code=" + e.code + " id=" + callId);
    VoxEngine.terminate();
}
