# Imports 
import tkinter as tk
import google.generativeai as genai

#global variables
content = ""
lang_entry = ""
export_btn = ""
data = ""
genai.configure(api_key="AIzaSyAziOtWmL9G6UiYYzxo1ewULBfCoqevh0w")
model = genai.GenerativeModel('gemini-1.5-flash')
#GUI & main function
def main():
    global lang_entry
    global data
    global export_btn
    
    root = tk.Tk()
    root.title("language generator")
    root.geometry("700x600")
    root.configure(background='#344C64')

    frame = tk.Frame(root, width=700, bg="#240750")
    frame.pack(padx=20, pady=20, fill = "x")
    
    lang_label = tk.Label(frame, text="Enter a new language : ", bg="#240750", fg="#fff", font=("Sans",18, "bold"))
    lang_label.pack()

    lang_entry = tk.Entry(frame, font=("Helvetica",12, "bold"), borderwidth=3)
    lang_entry.pack(padx=10, pady=10, fill = "x")

    lang_btn = tk.Button(frame, text="Generate Data", font=("Helvetica",12, "bold"), bg="#eee", command=generate)
    lang_btn.pack(padx=10, pady=10, ipadx=5, ipady=5, fill="x")
    
    dataframe = tk.Frame(root, width=700, bg="#577B8D")
    dataframe.pack(padx=20, pady=20, fill = "x")

    data = tk.Text(dataframe, height=17, borderwidth=5)
    data.pack(padx=20, pady=20)

    export_btn = tk.Button(dataframe, text="Export", font=("Helvetica",12, "bold"), bg="#eee", command=export)
    export_btn.pack(padx=10, pady=10, ipadx=5, ipady=5, fill="x")
    
    root.mainloop()


# Logic

def generate_data(lang):
    with open("keywords.json", "r")as f:
        sample = f.read()

    chat = model.start_chat(history=[])
    chat.send_message("you are a json keywords language translator, you recievle langauge name and data and change the translation to the new langauge, you translate programming keywords") 
    response = model.generate_content(f"generate the {lang} version of {sample} data, ony generate the data, don't explain it")

    data.insert("end", response.text.replace("```json", "").replace("```", ""))

def export():
    with open(f"{lang_entry.get()}_KW.json", "w", encoding="UTF-8") as f:
        f.write(data.get(0.1, "end"))
        
def generate():
    if lang_entry.get():
        generate_data(lang_entry.get())
    else:
        tk.messagebox.showerror("please enter a language")

main()
