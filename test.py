import streamlit as st
import os
import json
import re
import hmac
from datetime import datetime
import google.generativeai as genai

# ページ設定
st.set_page_config(
    page_title="英語リスニング練習アプリ",
    page_icon="🎧",
    layout="wide"
)

# パスワード検証関数
def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if hmac.compare_digest(st.session_state["password"], st.secrets["password"]):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # パスワードをセッションステートから削除
        else:
            st.session_state["password_correct"] = False
    
    if "password_correct" not in st.session_state:
        # First run, show input for password.
        st.text_input(
            "パスワードを入力してください", type="password", on_change=password_entered, key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        # Password incorrect, show input + error.
        st.text_input(
            "パスワードを入力してください", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 パスワードが違います")
        return False
    else:
        # Password correct.
        return True

# パスワードチェック
if not check_password():
    st.stop()

# カスタムCSS
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        margin-top: 10px;
    }
    .speaker-info {
        padding: 10px;
        background-color: #e8f0fe;
        border-radius: 5px;
        margin: 10px 0;
    }
    .text-display {
        padding: 20px;
        background-color: #f8f9fa;
        border-radius: 8px;
        border: 2px solid #e8eaed;
        font-size: 16px;
        line-height: 1.8;
        min-height: 200px;
    }
</style>
""", unsafe_allow_html=True)

# セッション状態の初期化
if 'generated_text' not in st.session_state:
    st.session_state.generated_text = ""
if 'speaker_gender' not in st.session_state:
    st.session_state.speaker_gender = "neutral"
if 'show_original_text' not in st.session_state:
    st.session_state.show_original_text = True
if 'text_visible' not in st.session_state:
    st.session_state.text_visible = False
if 'log_file_path' not in st.session_state:
    st.session_state.log_file_path = "theme_log.json"

# Gemini API初期化
@st.cache_resource
def initialize_gemini():
    try:
        # Streamlit Cloudのsecretsから取得
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        return genai.GenerativeModel('gemini-2.5-flash')
    except Exception as e:
        st.error(f"Gemini APIの初期化に失敗しました: {str(e)}")
        st.stop()

model = initialize_gemini()

# ログ機能
def load_theme_log():
    try:
        if os.path.exists(st.session_state.log_file_path):
            with open(st.session_state.log_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        st.warning(f"ログファイル読み込みエラー: {e}")
        return []

def save_theme_log(theme_entry):
    try:
        log_data = load_theme_log()
        log_data.append(theme_entry)
        with open(st.session_state.log_file_path, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.warning(f"ログファイル保存エラー: {e}")

def get_recent_themes(limit=5):
    try:
        log_data = load_theme_log()
        if not log_data:
            return []
        recent_logs = log_data[-limit:] if len(log_data) >= limit else log_data
        return [log_entry["theme"] for log_entry in recent_logs]
    except Exception as e:
        return []

def extract_theme_and_gender(text):
    try:
        prompt = f"""
        以下の英語文章について2つのことを分析してください:

        1. 主要なテーマやトピックを簡潔に日本語で要約してください(1-2文)
        2. この文章の話者や主人公の性別を判定してください(male/female/neutral)

        文章:
        {text}

        以下の形式で回答してください:
        テーマ: [テーマの説明]
        性別: [male/female/neutral]
        """
        
        response = model.generate_content(prompt)
        result = response.text.strip()
        
        theme = "テーマ抽出に失敗しました"
        gender = "neutral"
        
        lines = result.split('\n')
        for line in lines:
            if line.startswith('テーマ:'):
                theme = line.replace('テーマ:', '').strip()
            elif line.startswith('性別:'):
                gender_text = line.replace('性別:', '').strip().lower()
                if gender_text in ['male', 'female', 'neutral']:
                    gender = gender_text
        
        return theme, gender
    except Exception as e:
        st.warning(f"テーマ・性別抽出エラー: {e}")
        return "テーマ抽出に失敗しました", "neutral"

def hide_word_endings(text):
    def hide_word(match):
        word = match.group(0)
        if len(word) <= 2:
            return word
        else:
            return word[:2] + '-' * (len(word) - 2)
    
    pattern = r'\b[a-zA-Z]+(?:\'[a-zA-Z]+)?\b'
    return re.sub(pattern, hide_word, text)

def generate_text(cefr_level, word_count):
    with st.spinner('文章を生成中...'):
        try:
            recent_themes = get_recent_themes()
            
            base_prompt = f"""
            Create an English text passage suitable for an English language learner at CEFR level {cefr_level}.
            The passage should be approximately {word_count} words long.
            The content should be interesting, educational, and appropriate for language learning.
            """
            
            if recent_themes:
                themes_text = "\n".join([f"- {theme}" for theme in recent_themes])
                avoidance_prompt = f"""
                
                IMPORTANT: Please avoid creating content that is similar to these recently used themes:
                {themes_text}
                
                Choose a completely different topic or approach to ensure variety and prevent repetition.
                """
                prompt = base_prompt + avoidance_prompt
            else:
                prompt = base_prompt
            
            prompt += "\n\nOnly return the text passage without any additional explanations or metadata."
            
            response = model.generate_content(prompt)
            generated_text = response.text.strip()
            
            # テーマと性別を抽出
            theme, gender = extract_theme_and_gender(generated_text)
            
            # ログに保存
            theme_entry = {
                "timestamp": datetime.now().isoformat(),
                "cefr_level": cefr_level,
                "word_count": word_count,
                "theme": theme,
                "speaker_gender": gender,
                "text_preview": generated_text[:100] + "..." if len(generated_text) > 100 else generated_text
            }
            save_theme_log(theme_entry)
            
            st.session_state.generated_text = generated_text
            st.session_state.speaker_gender = gender
            st.session_state.text_visible = False
            st.session_state.show_original_text = True
            
            st.success("文章の生成が完了しました!")
            
        except Exception as e:
            st.error(f"テキスト生成に失敗しました: {str(e)}")

# Web Speech API用のJavaScript関数
def render_speech_controls():
    display_text = st.session_state.generated_text
    if not st.session_state.show_original_text:
        display_text = hide_word_endings(display_text)
    
    # JavaScriptエスケープ
    escaped_text = display_text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
    
    html_code = f"""
    <div style="margin-top: 20px;">
        <div style="background-color: #f8f9fa; padding: 16px; border-radius: 8px; border: 1px solid #e8eaed; margin-bottom: 16px;">
            <label style="font-weight: 500; margin-bottom: 12px; display: block;">読み上げ速度</label>
            <div style="display: flex; gap: 8px; margin-bottom: 12px;">
                <button class="speed-btn" data-speed="0.7" style="padding: 8px 16px; border: 2px solid #e8eaed; background: white; border-radius: 20px; cursor: pointer; flex: 1;">遅い</button>
                <button class="speed-btn active" data-speed="1.0" style="padding: 8px 16px; border: 2px solid #4285f4; background: #4285f4; color: white; border-radius: 20px; cursor: pointer; flex: 1;">標準</button>
                <button class="speed-btn" data-speed="1.3" style="padding: 8px 16px; border: 2px solid #e8eaed; background: white; border-radius: 20px; cursor: pointer; flex: 1;">速い</button>
            </div>
            
            <label style="font-weight: 500; margin-bottom: 8px; display: block;">話者選択</label>
            <select id="voiceSelect" style="width: 100%; padding: 12px; border: 2px solid #e8eaed; border-radius: 8px;">
                <option value="">読み込み中...</option>
            </select>
            
            <div style="margin-top: 12px;">
                <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                    <input type="checkbox" id="randomVoice" style="width: 18px; height: 18px;">
                    <span style="font-size: 14px;">ランダム話者で読み上げ(文章内で統一)</span>
                </label>
            </div>
        </div>
        
        <button id="playButton" style="width: 100%; padding: 16px; background: #34a853; color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 500; cursor: pointer;">
            <span id="playIcon">▶️</span>
            <span id="playText">読み上げ開始</span>
        </button>
        
        <div id="status" style="margin-top: 16px; padding: 12px; background: #e8f0fe; border-radius: 8px; text-align: center; display: none;"></div>
    </div>

    <script>
        (function() {{
            const textToSpeak = "{escaped_text}";
            let voices = [];
            let englishVoices = [];
            let currentSpeed = 1.0;
            let isPlaying = false;
            let selectedVoice = null;
            
            const voiceSelect = document.getElementById('voiceSelect');
            const playButton = document.getElementById('playButton');
            const playIcon = document.getElementById('playIcon');
            const playText = document.getElementById('playText');
            const status = document.getElementById('status');
            const randomVoiceCheckbox = document.getElementById('randomVoice');
            const speedButtons = document.querySelectorAll('.speed-btn');
            
            function loadVoices() {{
                voices = speechSynthesis.getVoices();
                englishVoices = voices.filter(voice => 
                    voice.lang.startsWith('en-') || voice.lang === 'en'
                );
                updateVoiceSelect();
            }}
            
            function updateVoiceSelect() {{
                voiceSelect.innerHTML = '';
                if (englishVoices.length === 0) {{
                    voiceSelect.innerHTML = '<option value="">英語音声が見つかりません</option>';
                    return;
                }}
                
                const defaultOption = document.createElement('option');
                defaultOption.value = '';
                defaultOption.textContent = 'デフォルト音声';
                voiceSelect.appendChild(defaultOption);
                
                englishVoices.forEach((voice, index) => {{
                    const option = document.createElement('option');
                    option.value = index;
                    option.textContent = `${{voice.name}} (${{voice.lang}})`;
                    voiceSelect.appendChild(option);
                }});
            }}
            
            function showStatus(message, isError = false) {{
                status.textContent = message;
                status.style.display = 'block';
                status.style.background = isError ? '#fce8e6' : '#e8f0fe';
                status.style.color = isError ? '#d93025' : '#1967d2';
                
                if (!isError) {{
                    setTimeout(() => {{
                        status.style.display = 'none';
                    }}, 3000);
                }}
            }}
            
            function startSpeech() {{
                if (!textToSpeak) {{
                    showStatus('読み上げるテキストがありません', true);
                    return;
                }}
                
                speechSynthesis.cancel();
                
                let voiceToUse = selectedVoice;
                if (randomVoiceCheckbox.checked && englishVoices.length > 0) {{
                    const randomIndex = Math.floor(Math.random() * englishVoices.length);
                    voiceToUse = englishVoices[randomIndex];
                }}
                
                const utterance = new SpeechSynthesisUtterance(textToSpeak);
                utterance.rate = currentSpeed;
                utterance.pitch = 1;
                utterance.volume = 1;
                
                if (voiceToUse) {{
                    utterance.voice = voiceToUse;
                    showStatus(`読み上げ中: ${{voiceToUse.name}} (速度: ${{currentSpeed}}x)`);
                }} else {{
                    showStatus(`読み上げ中 (速度: ${{currentSpeed}}x)`);
                }}
                
                utterance.onstart = () => {{
                    isPlaying = true;
                    playButton.style.background = '#ea4335';
                    playIcon.textContent = '⏸️';
                    playText.textContent = '停止';
                }};
                
                utterance.onend = () => {{
                    isPlaying = false;
                    playButton.style.background = '#34a853';
                    playIcon.textContent = '▶️';
                    playText.textContent = '読み上げ開始';
                    showStatus('読み上げが完了しました');
                }};
                
                utterance.onerror = (event) => {{
                    isPlaying = false;
                    playButton.style.background = '#34a853';
                    playIcon.textContent = '▶️';
                    playText.textContent = '読み上げ開始';
                    showStatus(`エラーが発生しました: ${{event.error}}`, true);
                }};
                
                speechSynthesis.speak(utterance);
            }}
            
            function stopSpeech() {{
                speechSynthesis.cancel();
                isPlaying = false;
                playButton.style.background = '#34a853';
                playIcon.textContent = '▶️';
                playText.textContent = '読み上げ開始';
                showStatus('読み上げを停止しました');
            }}
            
            // イベントリスナー
            speedButtons.forEach(btn => {{
                btn.addEventListener('click', (e) => {{
                    speedButtons.forEach(b => {{
                        b.style.border = '2px solid #e8eaed';
                        b.style.background = 'white';
                        b.style.color = 'black';
                    }});
                    e.target.style.border = '2px solid #4285f4';
                    e.target.style.background = '#4285f4';
                    e.target.style.color = 'white';
                    currentSpeed = parseFloat(e.target.dataset.speed);
                }});
            }});
            
            voiceSelect.addEventListener('change', (e) => {{
                const selectedIndex = e.target.value;
                selectedVoice = selectedIndex ? englishVoices[selectedIndex] : null;
            }});
            
            randomVoiceCheckbox.addEventListener('change', (e) => {{
                voiceSelect.disabled = e.target.checked;
            }});
            
            playButton.addEventListener('click', () => {{
                if (isPlaying) {{
                    stopSpeech();
                }} else {{
                    startSpeech();
                }}
            }});
            
            // 音声読み込み
            loadVoices();
            if (speechSynthesis.onvoiceschanged !== undefined) {{
                speechSynthesis.onvoiceschanged = loadVoices;
            }}
        }})();
    </script>
    """
    
    st.components.v1.html(html_code, height=350)

# メインUI
st.title("🎧 英語リスニング・リーディング練習アプリ")
st.markdown("**Gemini AI**で文章を生成し、**ブラウザのWeb Speech API**で読み上げを行います")

# サイドバー - パラメータ設定
with st.sidebar:
    st.header("⚙️ パラメータ設定")
    
    cefr_level = st.selectbox(
        "CEFRレベル",
        ["A0", "A1", "A2", "B1", "B2", "C1"],
        index=2
    )
    
    word_count = st.slider(
        "単語数",
        min_value=10,
        max_value=1000,
        value=100,
        step=10
    )
    
    if st.button("📝 文章を生成", type="primary", use_container_width=True):
        generate_text(cefr_level, word_count)

# メインエリア
if st.session_state.generated_text:
    # 話者情報
    gender_display = {"male": "男性", "female": "女性", "neutral": "中性"}.get(
        st.session_state.speaker_gender, "中性"
    )
    st.markdown(f'<div class="speaker-info">👤 話者: {gender_display}</div>', unsafe_allow_html=True)
    
    # 音声コントロール
    st.subheader("🔊 音声読み上げ")
    render_speech_controls()
    
    # テキスト表示コントロール
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📄 テキストを表示/非表示", use_container_width=True):
            st.session_state.text_visible = not st.session_state.text_visible
    
    with col2:
        if st.session_state.text_visible:
            if st.button(
                "🔤 単語を隠す/表示" if st.session_state.show_original_text else "✨ 全文を表示",
                use_container_width=True
            ):
                st.session_state.show_original_text = not st.session_state.show_original_text
    
    # テキスト表示エリア
    if st.session_state.text_visible:
        st.subheader("📖 生成されたテキスト")
        display_text = st.session_state.generated_text
        if not st.session_state.show_original_text:
            display_text = hide_word_endings(display_text)
        
        st.markdown(f'<div class="text-display">{display_text}</div>', unsafe_allow_html=True)

else:
    st.info("👈 左のサイドバーから「文章を生成」ボタンをクリックして開始してください")
    
    # 使い方
    with st.expander("📚 使い方"):
        st.markdown("""
        1. **サイドバー**でCEFRレベルと単語数を設定
        2. **文章を生成**ボタンをクリック
        3. 生成された文章が表示されます
        4. **読み上げ速度**と**話者**を選択
        5. **読み上げ開始**ボタンで音声再生
        6. **テキストを表示**ボタンでテキストの確認
        7. **単語を隠す**ボタンでリスニング練習
        
        ※ ブラウザのWeb Speech APIを使用しているため、インターネット接続が必要です
        ※ 過去5件のテーマは自動的に避けられます
        """)

# フッター
st.markdown("---")
st.markdown("Made with Streamlit 🎈 | Powered by Gemini AI 🤖 | Speech by Web Speech API 🗣️")

