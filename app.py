import pytesseract
from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
from PIL import Image, ImageOps
import google.generativeai as genai
import os
import csv
import pandas as pd
from io import StringIO

# Tesseractのパスを指定
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# APIキーの設定
genai.configure(api_key="AIzaSyBm77LRhPyDpu0an7ES2ax3Ee2ewAJ7rnU")

app = Flask(__name__)
app.secret_key = "your_secret_key"

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'tiff'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def preprocess_image(image):
    try:
        # グレースケール変換
        image = image.convert('L')
        # 自動コントラスト調整
        image = ImageOps.autocontrast(image)
        # 二値化処理（適切な閾値を設定）
        threshold = 140
        image = image.point(lambda p: p > threshold and 255)
        # 解像度の向上（拡大処理）
        image = image.resize((image.width * 2, image.height * 2), Image.LANCZOS)  # Image.LANCZOSを使用
        return image
    except Exception as e:
        print(f"Error in image processing: {e}")
        return None

def save_to_csv(extracted_text, generated_response):
    try:
        # CSVファイルの保存先を指定
        csv_file_path = 'output.csv'
        with open(csv_file_path, mode='a', newline='', encoding='utf-8-sig') as file:
            writer = csv.writer(file)
            writer.writerow([extracted_text, generated_response])
            print(f'Results saved to {csv_file_path}')
    except Exception as e:
        print(f"Error saving to CSV: {e}")


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            try:
                image = Image.open(file)
                # 画像の前処理を実行
                processed_image = preprocess_image(image)
                if processed_image is None:
                    flash('Image processing failed')
                    return redirect(request.url)

                # Tesseractのカスタム設定
                custom_config = r'--oem 3 --psm 6'
                text = pytesseract.image_to_string(processed_image, lang='jpn', config=custom_config)  # 日本語テキストの抽出
                ls = [[0, 0],[0, 0]]
                
                while len(ls[0]) != 4:
                    # Generative AIでの復元処理
                    model = genai.GenerativeModel('gemini-pro')
                    question = f"""テキスト内容：{text}
                    以下の作業を順に行ってください
                    ①レシートに書かれた以下の文章から以下の項目を抽出してください(出力はせず)
                    店舗名：レシートに記載されている店舗の名前を抽出してください。
                    住所：レシートに記載されている店舗の住所を抽出してください。
                    購入日：レシートの日付（年月日、ただし日付型で記入）が記載されている部分を抽出してください。
                    商品リスト：購入した商品名、その数量（数字のみ）、価格を抽出してリスト形式で出力してください。
                    合計金額：合計金額を抽出して提示してください。
                    ②テキスト内の丸数字（①、②、③など）を普通の数字（1、2、3など、int型）に変換してください。
                    ③すべての丸数字を対応する普通の数字に置き換えたテキストを出力してください。
                    ④全ての「*」を消してください。
                    ⑤上記の内容を以下出力例のように出力してください（応答の出力は⑤の結果だけで、①から④の出力はしないでください。）
                    出力例は以下の通りです
                    日付:yyy/MM/dd
                    商品1の商品名 商品1の個数 商品1の金額 商品1の個数×商品1の金額の値
                    商品2の商品名 商品2の個数 商品2の金額 商品2の個数×商品2の金額の値
                    商品3の商品名 商品3の個数 商品3の金額 商品3の個数×商品3の金額の値
                    
                    
                    """
                    response = model.generate_content(question)
                    generated_text = response.text
                    print("Extracted Text:", text)
                    print("Generated Response:", generated_text)
                
                    generated_text = generated_text.split('\n')
                
                    date = generated_text[0]
                
                    ls = []
                
                    for i in range(1, len(generated_text)-1):
                        product = generated_text[i].split(' ')
                        ls.append(product)
                        ls_sub = ls
                        
                return render_template('index.html', date=date, ls=ls)
                            
                
                # CSVファイルに結果を保存
                save_to_csv(text, generated_text)

            except Exception as e:
                print(f"Error: {e}")
                flash('An error occurred during processing.')
                return redirect(request.url)
        else:
            flash('Invalid file format. Please upload a PNG, JPG, or TIFF file.')
            return redirect(request.url)
    return render_template('index.html')


# グローバル変数としてls2を初期化
ls2 = []

@app.route('/clear_table', methods=['POST'])
def clear_table():
    global ls2  # `ls`データをグローバルスコープで使用
    ls2.clear()  # リストを空にしてデータを削除
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)