import streamlit as st
import google.generativeai as genai
import random
from pathlib import Path
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import hmac


# Gemini APIの設定
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# モデルの設定
model = genai.GenerativeModel('gemini-1.5-flash-002')

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
def init_session_state():
    states = {
        'japanese_text': None,
        'english_text': None,
        'quiz_sentence': None,
        'file_uploaded': False,
        'english_converted': False,
        'keywords': '',
        'word_count': 200
    }
    for key, value in states.items():
        if key not in st.session_state:
            st.session_state[key] = value

def reset_session():
    for key in st.session_state:
        if key != 'target_score':  # Preserve target score
            st.session_state[key] = None if not isinstance(st.session_state[key], bool) else False
    st.session_state.word_count = 200
    st.session_state.keywords = ''

def regenerate_text():
    st.session_state.english_text = None
    st.session_state.quiz_sentence = None
    st.session_state.english_converted = False

def create_text_image(text, width=800, height=400, font_size=80, is_english=True):
    """テキストを表示する画像を作成する関数"""
    image = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(image)
    
    # 日本語と英語で異なるフォントを使用
    if is_english:
        try:
            # 英語用フォント
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("DejaVuSans.ttf", font_size)
            except:
                font = ImageFont.load_default()
                font_size = 24
    else:
        try:
            # Ubuntu/Debian系の日本語フォント
            font = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", font_size)
        except:
            try:
                # Alpine Linuxの日本語フォント
                font = ImageFont.truetype("/usr/share/fonts/noto/NotoSansCJK-Bold.ttc", font_size)
            except:
                try:
                    # フォントがない場合、Google Fontsから日本語フォントをダウンロード
                    import requests
                    import tempfile
                    import os

                    # Noto Sans JP (Bold)をダウンロード
                    font_url = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/Japanese/NotoSansJP-Bold.otf"
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.otf') as f:
                        response = requests.get(font_url)
                        f.write(response.content)
                        font_path = f.name
                    
                    font = ImageFont.truetype(font_path, font_size)
                    
                    # 一時ファイルを削除
                    os.unlink(font_path)
                except:
                    # すべての方法が失敗した場合、IPAフォントをダウンロード（最後の手段）
                    try:
                        font_url = "https://moji.or.jp/wp-content/ipafont/IPAfont/ipag00303.zip"
                        
                        import zipfile
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as f:
                            response = requests.get(font_url)
                            f.write(response.content)
                            zip_path = f.name
                        
                        with tempfile.TemporaryDirectory() as temp_dir:
                            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                                zip_ref.extractall(temp_dir)
                                font_path = os.path.join(temp_dir, 'ipag.ttf')
                                font = ImageFont.truetype(font_path, font_size)
                            
                        os.unlink(zip_path)
                    except:
                        # 最後の手段が失敗した場合
                        st.error("日本語フォントの読み込みに失敗しました。システム管理者に連絡してください。")
                        return None

    # テキストのサイズを取得して中央配置
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (width - text_width) // 2
    y = (height - text_height) // 2
    
    # 英語は青、日本語は赤で表示
    text_color = 'blue' if is_english else 'red'
    
    # フォントサイズに応じてオフセットを調整
    offset = 2 if font_size >= 80 else 1
    
    # 文字を太く見せるために同じ文字を少しずらして複数回描画
    for dx in [-offset, 0, offset]:
        for dy in [-offset, 0, offset]:
            draw.text((x + dx, y + dy), text, fill=text_color, font=font)
    
    return image
def generate_long_text(keywords, target_score, word_count):
    prompt = f"""
    Create an English text about the following keywords: {keywords}
    Requirements:
    - Use vocabulary and grammar suitable for TOEIC {target_score} level
    - Text should be approximately {word_count} words long
    - Use natural, flowing English
    """
    return model.generate_content(prompt).text

def convert_to_english(japanese_text, target_score):
    prompt = f"""
    以下の日本語をTOEIC {target_score}点レベルの英語に変換してください。
    できるだけ自然な英語で、{target_score}点レベルに適した語彙と文法を使用してください。

    日本語テキスト:
    {japanese_text}
    """
    return model.generate_content(prompt).text

def create_quiz(english_text):
    sentences = [s.strip() for s in english_text.split('.') if s.strip()]
    return random.choice(sentences)

def evaluate_translation(original_english, japanese_answer):
    prompt = f"""
    以下の英文に対する日本語訳を評価してください。
    100点満点で採点し、改善点があれば指摘してください。
    採点では単語/熟語と文法の取り扱いに重点を置いてください。

    英文: {original_english}
    提出された日本語訳: {japanese_answer}
    
    形式:
    点数: [数字のみ]
    コメント: [評価コメント]
    """
    return model.generate_content(prompt).text

def extract_vocabulary(english_text):
    prompt = f"""
    以下の英文から重要な単語と熟語を抽出してください。
    各項目に日本語訳も付けてください。

    英文:
    {english_text}
    
    形式:
    単語/熟語 - 日本語訳
    """
    return model.generate_content(prompt).text

def handle_translation_quiz(tab_name):
    if not st.session_state.quiz_sentence or st.button("新しい問題を出題", key=f"new_quiz_button_{tab_name}"):
        with st.spinner('問題を作成中...'):
            st.session_state.quiz_sentence = create_quiz(st.session_state.english_text)
    
    st.subheader("翻訳問題")
    st.write("以下の英文を日本語に訳してください：")
    st.write(st.session_state.quiz_sentence)
    
    user_translation = st.text_area("あなたの訳", "", key=f"translation_input_{tab_name}")
    if st.button("採点する", key=f"grade_button_{tab_name}") and user_translation:
        with st.spinner('採点中...'):
            evaluation = evaluate_translation(
                st.session_state.quiz_sentence,
                user_translation
            )
        st.write("評価結果:")
        st.write(evaluation)
    
    if st.checkbox("単語・熟語リストを表示", key=f"sentense_list_{tab_name}"):
        with st.spinner('単語・熟語を抽出中...'):
            if tab_name == "short":
                vocabulary = extract_vocabulary(st.session_state.quiz_sentence)
            elif tab_name == "long":
                vocabulary = extract_vocabulary(st.session_state.english_text)
        st.subheader("重要な単語・熟語リスト")
        st.write(vocabulary)

def main():
    st.title("TOEIC英語学習アプリ")
    init_session_state()
    
    st.sidebar.number_input(
        "目標TOEICスコアを入力してください",
        min_value=10, max_value=990, value=700, step=10,
        key='target_score'
    )

    col1, col2 = st.sidebar.columns(2)
    if col1.button("リセット"):
        reset_session()
        st.rerun()
    if col2.button("再生成") and st.session_state.english_converted:
        regenerate_text()
        st.rerun()

    tab1, tab2, tab3 = st.tabs(["短文翻訳", "長文翻訳", "単語フラッシュカード"])

    with tab1:
        uploaded_file = st.file_uploader(
            "日本語のテキストファイルをアップロードしてください",
            type=['txt'],
            key="txt_uploader",
            on_change=reset_session
        )

        if uploaded_file and not st.session_state.file_uploaded:
            with st.spinner('ファイルを読み込んでいます...'):
                st.session_state.japanese_text = uploaded_file.read().decode('utf-8')
                st.session_state.file_uploaded = True
            st.success('読み込み完了')
        
        if st.session_state.file_uploaded and not st.session_state.english_converted:
            if st.button("英語に変換", key="convert_short"):
                with st.spinner('英語に変換中...'):
                    st.session_state.english_text = convert_to_english(
                        st.session_state.japanese_text,
                        st.session_state.target_score,
                    )
                    st.session_state.english_converted = True
                st.success('変換完了')

        if st.session_state.english_converted:
            handle_translation_quiz("short")

    with tab2:
        keywords = st.text_input("テキストのキーワードを入力してください（カンマ区切り）", 
                               key='keywords')
        word_count = st.number_input("生成する文章の単語数", 
                                   min_value=50, max_value=500, value=200, step=50,
                                   key='word_count')
        
        if st.button("長文を生成", key="generate_long_button"):
            with st.spinner('長文を生成中...'):
                st.session_state.english_text = generate_long_text(
                    keywords, 
                    st.session_state.target_score,
                    word_count
                )
                st.session_state.english_converted = True
            st.success('生成完了')
            st.write(st.session_state.english_text)
            handle_translation_quiz("long")

        elif st.session_state.english_converted:
            st.write(st.session_state.english_text)
            handle_translation_quiz("long")

    with tab3:
        uploaded_csv = st.file_uploader(
            "CSVファイルをアップロードしてください",
            type=['csv'],
            key="csv_uploader"
        )
        
        if uploaded_csv is not None:
            df = pd.read_csv(uploaded_csv)
            
            if len(df.columns) >= 2:
                display_speed = st.slider('表示速度（秒）', 1.0, 5.0, 2.0)
                
                if st.button('スタート', key="flashcard_start"):
                    images = []
                    
                    for _, row in df.iterrows():
                        eng_img = create_text_image(str(row[0]), is_english=True)
                        images.append(eng_img)
                        
                        jpn_img = create_text_image(str(row[1]), is_english=False)
                        images.append(jpn_img)
                    
                    gif_buffer = BytesIO()
                    images[0].save(
                        gif_buffer,
                        format='GIF',
                        save_all=True,
                        append_images=images[1:],
                        duration=int(display_speed * 1000),
                        loop=0
                    )
                    
                    st.image(gif_buffer.getvalue())
            else:
                st.error('CSVファイルは少なくとも2列（英単語と日本語訳）が必要です。')
       
if __name__ == "__main__":
    if check_password():
        main()
