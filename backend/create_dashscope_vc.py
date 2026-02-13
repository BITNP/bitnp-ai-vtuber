from tokens import get_token
from tts.dashscope.voice_clone import *


query_voice_list(get_token('dashscope'))
# create_voice(get_token('dashscope'), "./backend/tts/ref_audio/paimeng.wav", "shumeiniang")