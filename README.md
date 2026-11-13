# RecuDown 2
| View 1 | View 2 | View 3 |
| :---: | :---: | :---: |
| ![Screenshot 1](images/screenshot1.png) | ![Screenshot 2](images/screenshot2.png) | ![Screenshot 3](images/screenshot3.png) |

This project is an original user interface built from scratch. It uses the open-source `recu-windows-amd64.exe` engine created by [@baconator696](https://github.com/baconator696) to handle the background downloads.

## Main Features

- **Flexible Download Modes:** Download multiple videos at the same time (Parallel Mode) or one by one in order (Series Mode).
- **Cookie Injection & Extraction (CDP):** Automatically retrieve your session cookies and User-Agent by connecting to your browser via the Chrome DevTools Protocol (CDP). No more manual copy-pasting.
- **Automatic Browser Detection:** On startup, the app searches for Chromium-based browsers (Chrome, Edge, Opera GX, Brave, Vivaldi, etc.) and launches them in debug mode to facilitate logging in.
- **Automatic Video Conversion:** If FFmpeg is installed on your system, the app will automatically convert downloaded `.ts` files to MP4 or MKV without losing quality.
- **Multi-language Support:** Interface fully translated into English, Spanish, Portuguese, and Russian.
- **Date-based Renaming Options:** Automatically organize your files using the Year-Month-Day format (YYYY-MM-DD), Day-Month-Year format (DD-MM-YYYY), or keep the original video name.
- **Automatic Backups:** Saves a history of your last 10 download configurations in a `backup.txt` file, so you never lose your progress.
- **Customizable UI:** Frameless window with an "Always on Top" option, a URL quantity selector, and confirmation sounds for clicks and completed downloads.

## How to Use (Windows)

1. Go to the Releases section on the right and download RecuDown.2.exe.
2. Run the file. You don't need to install Python or any additional libraries.
3. (Optional) If you have FFmpeg installed, the app will automatically convert the videos for you.

## Compiling from Source (Developers)

If you want to modify the code and compile it yourself, follow these steps. Note: All source code and asset files are located inside the files folder in this repository.

1. Install Python 3.10 or higher.
- **Option A (Web):** Download it from [python.org](https://www.python.org/). **Important:** During installation, make sure to check the box that says **"Add Python to PATH"**.
- **Option B (CMD):** If you have `winget` installed, open CMD and run: `winget install Python.Python.3.10`
2. Download or clone this repository (e.g., by downloading the `.zip` file). Extract the downloaded file and open the **`files`** folder.
3. **Get the download engine:** Download `recu-windows-amd64.exe` from [@baconator696's repository](https://github.com/baconator696/Recu-Download) and place it inside the **`files`** folder.
4. Open a Command Prompt (CMD) **inside the `files` folder**.
- *Easy way:* Open the `files` folder in File Explorer, click on the address bar at the top, type `cmd`, and press Enter.
5. Install the required Python dependencies:
   `python -m pip install -r requirements.txt`
6. Test the application from source (optional):
   `python RecuDown.py`
7. Build the final executable using PyInstaller. Run this command in Windows CMD:
```
   `pyinstaller --onefile --noconsole ^`
   `--add-binary "recu-windows-amd64.exe;." ^`
   `--add-binary "sound.wav;." ^`
   `--add-binary "tap.wav;." ^`
   `--add-data "icon.ico;." ^`
   `--icon=icon.ico ^`
   `--version-file=version_info.txt ^`
   `--hidden-import=websocket ^`
   `RecuDown.py`
   ```
*After the compilation finishes, you will find your final `.exe` file inside the newly created `dist` folder.*
## Credits

- **Download Engine:** [@baconator696](https://github.com/baconator696)
- **GUI & Code:** jorminyo2022

## License

Same as the original project.
