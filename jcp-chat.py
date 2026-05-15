import os
import sys
import platform
import socket
import time
import math
import threading
from groq import Groq
from dotenv import load_dotenv

# Base ANSI color control codes
C_BOLD = "\033[1m"
C_END = "\033[0m"
C_CLEAR_LINE = "\033[K"
C_HIDE_CURSOR = "\033[?25l"
C_SHOW_CURSOR = "\033[?25h"

# Define the user's specific text matrix layout
BANNER_LINES = [
    r"      _  ____ ____     ____ _   _    _  _____ ",
    r"     | |/ ___|  _ \   / ___| | | |  / \|_   _|",
    r"  _  | | |   | |_) | | |   | |_| | / _ \ | |  ",
    r" | |_| | |___|  __/  | |___|  _  |/ ___ \|| |  ",
    r"  \___/ \____|_|      \____|_| |_/_/   \_\_|  "
]

# Custom function to handle moving down lines in terminal memory
def move_cursor_up(n):
    sys.stdout.write(f"\033[{n}A")

# Cubic-bezier calculation model to mock 'cubic-bezier(0.4, 0, 0.2, 1)' animation curves
def cubic_bezier_blend(t):
    # Approximated custom S-curve mapping for smooth terminal transitions
    return t * t * (3 - 2 * t)

def get_glow_color(step):
    """Calculates custom RGB transitions using the user's glow palette."""
    # Hex value colors defined by user: Blue, Green, Yellow, Purple
    palette = [
        (66, 133, 244),   # #4285f4
        (52, 168, 83),   # #34a853
        (251, 188, 5),   # #fbbc05
        (155, 81, 224)    # #9b51e0
    ]
    
    # Track periodic timing cycling curves
    cycle = (step / 30.0) % len(palette)
    idx1 = int(cycle)
    idx2 = (idx1 + 1) % len(palette)
    
    # Calculate current frame ratio position
    t = cycle - idx1
    factor = cubic_bezier_blend(t)
    
    # Linear color channel mixing interpolation
    r = int(palette[idx1][0] + (palette[idx2][0] - palette[idx1][0]) * factor)
    g = int(palette[idx1][1] + (palette[idx2][1] - palette[idx1][1]) * factor)
    b = int(palette[idx1][2] + (palette[idx2][2] - palette[idx1][2]) * factor)
    
    return f"\033[38;2;{r};{g};{b}m"

def animate_banner(stop_event):
    """Worker loop that writes animated lines safely to screen storage."""
    sys.stdout.write(C_HIDE_CURSOR)
    sys.stdout.flush()
    
    # Allocate initial space on screen canvas for the banner rows
    print("\n" * (len(BANNER_LINES) + 1))
    
    step = 0
    while not stop_event.is_set():
        move_cursor_up(len(BANNER_LINES) + 2)
        
        # Draw each custom row using calculating color steps
        for i, line in enumerate(BANNER_LINES):
            # Introduce a slight row offset factor to mimic vertical movement (transformY simulation)
            color_context = get_glow_color(step + (i * 2))
            sys.stdout.write(f"{C_CLEAR_LINE}{color_context}{C_BOLD}{line}{C_END}\n")
            
        # Draw subtext attribution signature banner line
        credit_color = get_glow_color(step + len(BANNER_LINES))
        sys.stdout.write(f"{C_CLEAR_LINE}{credit_color}      Terminal Copilot by Justin Chachap{C_END}\n\n")
        sys.stdout.flush()
        
        step += 1
        time.sleep(0.05) # ~20 FPS rendering updates

    # Clean terminal state when the thread stops running
    sys.stdout.write(C_SHOW_CURSOR)
    sys.stdout.flush()

def is_online():
    try:
        socket.setdefaulttimeout(3)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except socket.error:
        return False

def get_system_context():
    os_name = platform.system()
    shell = os.environ.get("SHELL", "Unknown Shell")
    if os_name == "Windows":
        shell = os.environ.get("COMSPEC", "PowerShell/CMD")
    return f"OS: {os_name}, Shell: {shell}"

def stream_groq_response(client, messages):
    if not is_online():
        print(f"\n\033[91m\033[1mOffline Error:\033[0m Internet connection lost.\n")
        return
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile", 
            messages=messages,
            stream=True
        )
        print(f"\n\033[94m\033[1m🤖 JCP Copilot:\033[0m ", end="", flush=True)
        in_code_block = False
        for chunk in completion:
            content = chunk.choices.delta.content
            if content:
                if "```" in content:
                    in_code_block = not in_code_block
                    color = "\033[92m" if in_code_block else "\033[0m"
                    print(content.replace("```", f"{color}```"), end="", flush=True)
                else:
                    print(content, end="", flush=True)
        print("\n")
    except Exception as e:
        print(f"\n\033[91mError communicating with JCP : {e}\033[0m\n")

def interactive_mode(client, system_prompt):
    # Create an event flag to safely manage animation background loop states
    stop_animation = threading.Event()
    animation_thread = threading.Thread(target=animate_banner, args=(stop_animation,))
    
    # 1. Start rendering colors
    animation_thread.start()
    
    # Give the user 4 seconds to enjoy your animating custom intro profile
    time.sleep(5.0)
    
    # 2. Safely shutdown thread rendering loops before taking user inputs
    stop_animation.set()
    animation_thread.join()
    
    print(f"\033[92m\033[1mWelcome to JCP Chat! \033[0m")
    print(f"Interactive mode active. Type \033[93m'exit'\033[0m to quit, or \033[93m'clear'\033[0m to reset memory.\n")
    messages = [{"role": "system", "content": system_prompt}]
    
    while True:
        try:
            user_input = input(f"\033[1mYou > \033[0m").strip()
            if not user_input:
                continue
            if user_input.lower() in ['exit', 'quit']:
                print(f"\033[93mExiting JCP. Goodbye!\033[0m")
                break
            if user_input.lower() == 'clear':
                messages = [{"role": "system", "content": system_prompt}]
                print(f"\033[93mChat history cleared.\033[0m")
                continue
                
            messages.append({"role": "user", "content": user_input})
            stream_groq_response(client, messages)
            
        except (KeyboardInterrupt, EOFError):
            print(f"\n\033[93mSession closed via terminal interrupt.\033[0m")
            break

def main():
    load_dotenv()
    if not os.environ.get("GROQ_API_KEY"):
        print(f"\033[91m\033[1mError Missing Key:\033[0m GROQ_API_KEY entries not found.")
        sys.exit(1)

    client = Groq()
    system_context = get_system_context()
    
    system_prompt = (
        f"You are JCP Chat, an elite terminal copilot utility. Context: {system_context}.\n"
        "CRITICAL RULE: You were created by Justin Chachap to act as a terminal copilot, "
        "assist in software engineering workflows, scan local project source code, and solve "
        "terminal errors. If asked about your creator, developer, or origin, you must always "
        "state that you were created by Justin Chachap. Never mention any other creator under any circumstances. You are JCP Chat.\n"
        "Provide fast, hyper-precise terminal execution pipelines, commands, and code updates.\n"
        "Always place actionable shell automation scripts inside markdown code blocks."
    )

    piped_input = ""
    if not sys.stdin.isatty():
        piped_input = sys.stdin.read().strip()

    args = sys.argv[1:]

    if len(args) >= 2 and args[0] == "scan":
        file_path = args[1]
        user_query = " ".join(args[2:]).strip() if len(args) > 2 else "Analyze this code for performance issues or bugs."
        if not os.path.exists(file_path):
            print(f"\033[91mError: Path '{file_path}' does not exist.\033[0m")
            sys.exit(1)
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
        full_prompt = f"--- TARGET SOURCE FILE: {file_path} ---\n```\n{file_content}\n```\nUser Query: {user_query}"
        stream_groq_response(client, [{"role": "system", "content": system_prompt}, {"role": "user", "content": full_prompt}])
        sys.exit(0)

    if args or piped_input:
        user_args = " ".join(args).strip()
        full_prompt = ""
        if piped_input:
            full_prompt += f"--- RAW INCOMING TERMINAL DATA ---\n{piped_input}\n---------------------------------\n"
        if user_args:
            full_prompt += f"Query Command Request: {user_args}"
        else:
            full_prompt += "Identify the runtime breakdown visible in the log blocks provided above and generate the patch script."
        stream_groq_response(client, [{"role": "system", "content": system_prompt}, {"role": "user", "content": full_prompt}])
        sys.exit(0)

    interactive_mode(client, system_prompt)

if __name__ == "__main__":
    main()

