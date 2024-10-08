import streamlit as st
import google.generativeai as genai
import os
import json
import re
import hmac



# Gemini APIの設定
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# モデルの設定
model = genai.GenerativeModel('gemini-1.5-flash-002')

# セッション状態の初期化
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history=[])
if "quiz_questions" not in st.session_state:
    st.session_state.quiz_questions = []
if "text_questions" not in st.session_state:
    st.session_state.text_questions = []
if "current_question" not in st.session_state:
    st.session_state.current_question = 0
if "score" not in st.session_state:
    st.session_state.score = 0
if "num_questions" not in st.session_state:
    st.session_state.num_questions = 5  # デフォルトの問題数


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


# ローカルファイルの内容を抽出する関数
def extract_text_from_file(file):
    file_extension = os.path.splitext(file.name)[1].lower()
    
    if file_extension == '.txt':
        return file.getvalue().decode('utf-8')
    else:
        return "Unsupported file format"

def generate_multiple_choice_quiz(content, num_questions=5):
    prompt = f"""
    以下の内容に基づいて、{num_questions}問の4択問題を生成してください。各問題の作成には以下のプロセスを厳密に従ってください：

    1. **コンテンツ全体を満遍なく網羅するように、異なる部分から情報を選択**してください。

    2. 選択した情報に基づいて、**以下の手順で問題を構築**してください：
        a. まず、選択した情報の核心となる概念や事実を特定します。
        b. その概念や事実について、なぜ重要か、どのような意味を持つのかを考察します。
        c. 考察に基づいて、問題の解答となる理論や説明を構築します。
        d. 構築した理論や説明を基に、簡潔で明確な問題文を作成します。
        e. 正解となる選択肢を、構築した理論や説明から直接導き出します。
        f. 不正解の選択肢を、以下の条件を満たすように作成します：
            - 正解と関連性があり、一見もっともらしく見えるもの
            - 明らかに間違っているものは避ける
            - 正解と完全に反対の意味を持つものは避ける
            - お互いに矛盾する選択肢を含めない
            - 部分的に正しい内容や、状況によっては正解と解釈される可能性のある選択肢は避ける

    3. 問題文は以下の条件を厳守してください：
        - 明確で簡潔であること
        - **一つの明確な答えのみを問うもの**であること
        - **複数の解釈が可能な表現を避ける**こと
        - 曖昧な表現や主観的な言葉を使用しないこと

    4. すべての選択肢は、長さや詳細さのレベルが同程度になるようにしてください。

    5. 「すべて正しい」「すべて間違い」などの選択肢は使用しないでください。

    6. 数値を扱う問題の場合、選択肢の数値は適度に離れた値にしてください。

    7. 専門用語を使う場合は、内容に記載されているものに限定してください。

    8. 各問題の正解には、以下の要素を含む詳細な説明を付けてください：
        - **なぜその選択肢が唯一の正解なのか**の具体的な理由
        - 提供された内容からの直接的な引用や参照
        - 他の選択肢が不正解である明確な理由
        - 必要に応じて、この知識がどのように適用されるかの例や文脈

    9. 生成した問題を再確認し、複数の正解が可能な問題や曖昧な問題がないことを確認してください。

    10. テキストのフォーマットと改行については、以下のガイドラインに従ってください：
        - 箇条書きやリストを使用する場合は、Markdown記法を使用してください。
        - 強調したい部分は、アスタリスクを使用してください。例：**強調したいテキスト**
        - 説明文内で段落を分ける場合は、空行を入れてください。

    回答はJSON形式で提供してください。フォーマットは以下の通りです:

    {{
        "questions": [
            {{
                "question": "問題文",
                "choices": ["選択肢A", "選択肢B", "選択肢C", "選択肢D"],
                "correct_answer": "正解の選択肢",
                "explanation": "正解の詳細な根拠と説明、および他の選択肢が不正解である理由"
            }},
            // 他の問題...
        ]
    }}

    コンテンツ:
    {content}
    """

    with st.spinner('4択クイズを生成中...'):
        response = st.session_state.chat.send_message(prompt)
    
    # APIレスポンスからJSONらしき部分を抽出
    json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
    if json_match:
        json_str = json_match.group()
        json_str = json_str.replace('\\', '\\\\')
        
        try:
            quiz_data = json.loads(json_str)
            return quiz_data["questions"]
        except json.JSONDecodeError as e:
            st.error(f"JSONのパースに失敗しました: {e}")
            st.text(f"受け取ったJSON文字列: {json_str}")
            return []
    else:
        st.error("APIレスポンスからJSONを抽出できませんでした。")
        st.text(f"APIレスポンス: {response.text}")
        return []

def enhance_quiz_difficulty(quiz_data, model):
    enhanced_questions = []
    
    for question in quiz_data:
        prompt = f"""
        以下の4択問題をより高難度にしてください。ネット上の実例や論文情報を参考にし、以下の点に注意して問題を調整してください：

        1. 問題の深さを増す：より専門的な知識や応用力を問う
        2. 選択肢の複雑さを上げる：似通った選択肢を作成し、微妙な違いを識別する力を問う
        3. 最新の研究成果や議論を反映：可能であれば、その分野の最新のトレンドや論争点を含める
        4. 実世界との関連性を強化：理論的な知識を実践的な状況に適用する力を問う
        5. 問題の構造を複雑化：複数の概念を組み合わせた問題を作成する

        元の問題：
        {json.dumps(question, ensure_ascii=False, indent=2)}

        高難度版の問題をJSON形式で提供してください。フォーマットは元の問題と同じにしてください。
        """

        response = model.generate_content(prompt)
        
        # APIレスポンスからJSONらしき部分を抽出
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            try:
                enhanced_question = json.loads(json_str)
                enhanced_questions.append(enhanced_question)
            except json.JSONDecodeError as e:
                print(f"JSONのパースに失敗しました: {e}")
                print(f"受け取ったJSON文字列: {json_str}")
        else:
            print("APIレスポンスからJSONを抽出できませんでした。")
            print(f"APIレスポンス: {response.text}")

    return enhanced_questions


# 文章問題生成関数（新規追加）
def generate_text_based_quiz(content, num_questions=5):
    prompt = f"""
    以下の内容に基づいて、{num_questions}問の文章記述式問題を生成してください。各問題には以下の要素を含めてください：

    1. 問題文: 明確で簡潔であり、特定の情報や概念について説明を求めるものにしてください。
    2. 模範解答: 1〜3文程度の簡潔な説明を含む正解例を提供してください。
    3. キーポイント: 回答に含まれるべき重要な要素を3〜5点リストアップしてください。
    4. 解説: 模範解答の詳細な説明と、各キーポイントがなぜ重要なのかを説明してください。

    回答はJSON形式で提供してください。フォーマットは以下の通りです：

    {{
        "questions": [
            {{
                "question": "問題文",
                "model_answer": "模範解答",
                "key_points": ["キーポイント1", "キーポイント2", "キーポイント3"],
                "explanation": "回答の解説と採点基準"
            }},
            // 他の問題...
        ]
    }}

    コンテンツ:
    {content}
    """

    with st.spinner('文章問題を生成中...'):
        response = model.generate_content(prompt)
    
    # APIレスポンスからJSONらしき部分を抽出
    json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
    if json_match:
        json_str = json_match.group()
        json_str = json_str.replace('\\', '\\\\')
        
        try:
            quiz_data = json.loads(json_str)
            return quiz_data["questions"]
        except json.JSONDecodeError as e:
            st.error(f"JSONのパースに失敗しました: {e}")
            st.text(f"受け取ったJSON文字列: {json_str}")
            return []
    else:
        st.error("APIレスポンスからJSONを抽出できませんでした。")
        st.text(f"APIレスポンス: {response.text}")
        return []


def main():
    # Streamlitアプリのタイトル
    st.title("Gemini ChatBot with RAG and Quiz")

    # サイドバーにモード選択を追加
    mode = st.sidebar.radio("モード選択", ["チャット", "4択クイズ", "文章問題"])

    # 出題数の設定
    st.session_state.num_questions = st.sidebar.number_input("出題数", min_value=1, max_value=10, value=st.session_state.num_questions)

    # ファイルアップロード
    uploaded_file = st.sidebar.file_uploader("参照するファイルをアップロードしてください", type=['txt', 'pdf', 'docx'])

    if uploaded_file is not None:
        file_content = extract_text_from_file(uploaded_file)
        st.success(f"{uploaded_file.name} がアップロードされました。内容を参照して回答を生成します。")

    if mode == "チャット":
        # ユーザー入力
        user_input = st.text_input("メッセージを入力してください:")

        # 送信ボタン
        if st.button("送信"):
            # ユーザーメッセージをチャット履歴に追加
            st.session_state.messages.append({"role": "user", "content": user_input})

            # アップロードされたファイルがある場合、その内容を含めて質問を生成
            if uploaded_file is not None:
                prompt = f"以下の情報を参考にして質問に答えてください:\n\n{file_content}\n\n質問: {user_input}"
            else:
                prompt = user_input

            # Gemini APIを使用して応答を生成
            response = st.session_state.chat.send_message(prompt)

            # ボットの応答をチャット履歴に追加
            st.session_state.messages.append({"role": "assistant", "content": response.text})

        # チャット履歴の表示
        for message in st.session_state.messages:
            if message["role"] == "user":
                st.text_input("You:", value=message["content"], disabled=True)
            else:
                st.text_area("Bot:", value=message["content"], disabled=True)

        # 履歴クリアボタン
        if st.button("履歴をクリア"):
            st.session_state.messages = []
            st.session_state.chat = model.start_chat(history=[])
            st.rerun()

    elif mode == "4択クイズ":
        if uploaded_file is None:
            st.warning("クイズを生成するには、まずファイルをアップロードしてください。")
        else:
            difficulty = st.radio("難易度を選択してください:", ["通常", "高難度"])
            
            if "quiz_questions" not in st.session_state or len(st.session_state.quiz_questions) == 0:
                if st.button("4択クイズを生成"):
                    st.session_state.quiz_questions = generate_multiple_choice_quiz(file_content, st.session_state.num_questions)

                    if difficulty == "高難度":
                        with st.spinner('高難度問題を生成中...'):
                            st.session_state.quiz_questions = enhance_quiz_difficulty(st.session_state.quiz_questions, model)
                            
                    st.session_state.current_question = 0
                    st.session_state.score = 0
                    st.session_state.quiz_completed = False
                    st.session_state.answered = False
                    st.session_state.last_answer_correct = None
                    st.rerun()

            if "quiz_questions" in st.session_state and len(st.session_state.quiz_questions) > 0:
                if not st.session_state.quiz_completed:
                    current_q = st.session_state.quiz_questions[st.session_state.current_question]
                    st.write(f"質問 {st.session_state.current_question + 1}:")
                    st.write(current_q["question"])
                    
                    user_answer = st.radio("答えを選択してください:", current_q["choices"], key=f"q_{st.session_state.current_question}")
                    
                    if not st.session_state.answered:
                        if st.button("回答", key=f"submit_{st.session_state.current_question}"):
                            is_correct = user_answer == current_q["correct_answer"]
                            if is_correct:
                                st.session_state.score += 1
                            st.session_state.answered = True
                            st.session_state.last_answer_correct = is_correct
                            st.rerun()
                    else:
                        if st.session_state.last_answer_correct:
                            st.success("正解!")
                        else:
                            st.error(f"不正解。正解は: {current_q['correct_answer']}")
                                        
                        st.write("説明:")
                        st.write(current_q['explanation'])

                        if st.button("次の質問へ", key=f"next_{st.session_state.current_question}"):
                            st.session_state.current_question += 1
                            st.session_state.answered = False
                            st.session_state.last_answer_correct = None
                            if st.session_state.current_question >= len(st.session_state.quiz_questions):
                                st.session_state.quiz_completed = True
                            st.rerun()

                else:
                    st.write(f"クイズ終了! あなたのスコア: {st.session_state.score}/{len(st.session_state.quiz_questions)}")
                    if st.button("クイズをリセット", key="reset_end"):
                        st.session_state.quiz_questions = []
                        st.session_state.current_question = 0
                        st.session_state.score = 0
                        st.session_state.quiz_completed = False
                        st.session_state.answered = False
                        st.session_state.last_answer_correct = None
                        st.rerun()

    elif mode == "文章問題":
        if uploaded_file is None:
            st.warning("問題を生成するには、まずファイルをアップロードしてください。")
        else:
            if "text_questions" not in st.session_state or len(st.session_state.text_questions) == 0:
                if st.button("文章問題を生成"):
                    st.session_state.text_questions = generate_text_based_quiz(file_content, st.session_state.num_questions)
                    st.session_state.current_question = 0
                    st.session_state.score = 0
                    st.session_state.quiz_completed = False
                    st.session_state.answered = False
                    st.rerun()

            if "text_questions" in st.session_state and len(st.session_state.text_questions) > 0:
                if not st.session_state.quiz_completed:
                    current_q = st.session_state.text_questions[st.session_state.current_question]
                    st.write(f"質問 {st.session_state.current_question + 1}:")
                    st.write(current_q["question"])
                    
                    user_answer = st.text_area("回答を入力してください:", key=f"q_{st.session_state.current_question}")
                    
                    if not st.session_state.answered:
                        if st.button("回答", key=f"submit_{st.session_state.current_question}"):
                            # 簡易的な採点（キーポイントの一致度で評価）
                            key_points_matched = sum(point.lower() in user_answer.lower() for point in current_q["key_points"])
                            score = key_points_matched / len(current_q["key_points"])
                            st.session_state.score += score
                            st.session_state.answered = True
                            st.rerun()
                    else:
                        st.write("模範解答:")
                        st.write(current_q['model_answer'])
                        
                        st.write("キーポイント:")
                        for point in current_q['key_points']:
                            st.write(f"- {point}")
                        
                        st.write("解説:")
                        st.write(current_q['explanation'])

                        if st.button("次の質問へ", key=f"next_{st.session_state.current_question}"):
                            st.session_state.current_question += 1
                            st.session_state.answered = False


    # クイズリセットボタン（クイズモード以外でも表示）
    if ("quiz_questions" in st.session_state and len(st.session_state.quiz_questions) > 0) or \
    ("text_questions" in st.session_state and len(st.session_state.text_questions) > 0):
        if st.button("クイズをリセット", key="reset_global"):
            st.session_state.quiz_questions = []
            st.session_state.text_questions = []
            st.session_state.current_question = 0
            st.session_state.score = 0
            st.session_state.quiz_completed = False
            st.session_state.answered = False
            st.session_state.last_answer_correct = None
            st.session_state.chat = model.start_chat(history=[])
            st.rerun()

# パスワード認証をチェックしてからメインアプリケーションを実行
if check_password():
    main()
