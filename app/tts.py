import os
import queue
import threading

os.environ.setdefault("COQUI_TOS_AGREED", "1")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFERENCE_VOICE = os.path.join(BASE_DIR, "tts_models", "speaker_samples", "speaker_120.mp3")
MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
SAMPLE_RATE = 24000

SYNTHESIS_PARAMS = dict(
    language="de",
    temperature=0.65,
    repetition_penalty=4.0,
    top_p=0.85,
)


class TextToSpeech(threading.Thread):
    """Local neural voice-cloned text-to-speech (Coqui XTTS-v2, fully
    offline, GPU-accelerated). Streams audio chunk-by-chunk as they're
    generated instead of waiting for the whole sentence, so the first
    sound comes back in under a second instead of several seconds. Runs
    on its own thread so speaking a response never blocks the audio-
    recognition loop."""

    def __init__(self, reference_voice: str = REFERENCE_VOICE):
        super().__init__(daemon=True)
        self._queue = queue.Queue()
        self._stop_event = threading.Event()
        self._reference_voice = reference_voice
        self._model = None
        self._gpt_cond_latent = None
        self._speaker_embedding = None

    def speak(self, text: str, on_done=None):
        self._queue.put((text, on_done))

    def stop(self):
        self._stop_event.set()
        self._queue.put(None)

    def run(self):
        self._load_model()

        while not self._stop_event.is_set():
            item = self._queue.get()
            if item is None:
                continue
            text, on_done = item
            try:
                self._synthesize_and_play(text)
            except Exception:
                pass
            if on_done:
                try:
                    on_done()
                except Exception:
                    pass

    def _load_model(self):
        from TTS.tts.configs.xtts_config import XttsConfig
        from TTS.tts.models.xtts import Xtts
        from TTS.utils.manage import ModelManager

        model_path = ModelManager().download_model(MODEL_NAME)[0]
        config = XttsConfig()
        config.load_json(os.path.join(model_path, "config.json"))
        model = Xtts.init_from_config(config)
        model.load_checkpoint(config, checkpoint_dir=model_path, eval=True)
        model.cuda()

        self._model = model
        self._gpt_cond_latent, self._speaker_embedding = model.get_conditioning_latents(
            audio_path=[self._reference_voice]
        )

    def _synthesize_and_play(self, text: str):
        import numpy as np
        import sounddevice as sd

        stream = self._model.inference_stream(
            text, SYNTHESIS_PARAMS["language"], self._gpt_cond_latent, self._speaker_embedding,
            temperature=SYNTHESIS_PARAMS["temperature"],
            repetition_penalty=SYNTHESIS_PARAMS["repetition_penalty"],
            top_p=SYNTHESIS_PARAMS["top_p"],
        )

        with sd.OutputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32") as out:
            for chunk in stream:
                audio = chunk.detach().cpu().numpy().astype(np.float32)
                out.write(audio.reshape(-1, 1))
