# RecuDown 2
**Read this in:** [English](README.md) | [Español](README_es.md)

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

## Requirements & Browser Compatibility

- **Account:** You must have a valid and active trial account on the target site to use this application.
- **Browser Profile:** The app creates and configures a specific browser profile automatically. Ensure you are using this profile when logging in.
- **Compatible Browsers:** Chrome, Edge, Brave, Opera, Opera GX, Slimjet, and Vivaldi (Chromium-based).
- **Incompatible Browsers:** Firefox and Safari (these will not work with the CDP integration).
- **How to set your default browser:** Search for "Default apps" in your Windows settings. Under "Web browser", select one of the compatible browsers listed above.

## How to Use (Windows)

1. Go to the Releases section on the right and download RecuDown.2.exe.
2. Run the file. You don't need to install Python or any additional libraries.
3. (Optional) If you have FFmpeg installed, the app will automatically convert the videos for you.

## Compiling from Source (Developers)

If you want to modify the code and compile it yourself, follow these steps:

1. Install Python 3.10 or higher.
- **Option A (CMD - Easiest and fastest):** Open CMD **as Administrator** (Right-click -> Run as administrator) and run: `winget install Python.Python.3.10`
- **Option B (Web):** Download it from [python.org](https://www.python.org/). **Important:** During installation, make sure to check the box that says **"Add Python to PATH"**.
2. Download or clone this repository (e.g., by downloading the `.zip` file). Extract the downloaded file and open the **`files`** folder.
3. **Get the download engine:** Download `recu-windows-amd64.exe` from the repository of [@baconator696](https://github.com/baconator696/Recu-Download/releases/tag/v1.11.8) and place it inside the **`files`** folder.
4. Open a Command Prompt (CMD) **inside the `files` folder**.
- *Easy way:* Open the `files` folder in File Explorer, click on the address bar at the top, type `cmd`, and press Enter.
5. **In the CMD window**, install the required Python dependencies by running:
   `python -m pip install -r requirements.txt`
6. *(Optional)* **In the same CMD window**, test the application from source by running:
   `python RecuDown.py`
7. Build the final executable using PyInstaller. Run this command in the Windows command line (CMD):
```
pyinstaller --onefile --noconsole ^
--add-binary "recu-windows-amd64.exe;." ^
--add-binary "sound.wav;." ^
--add-binary "tap.wav;." ^
--add-data "icon.ico;." ^
--icon=icon.ico ^
--version-file=version_info.txt ^
--hidden-import=websocket ^
RecuDown.py
   ```
*After the compilation finishes, you will find your final `.exe` file inside the newly created `dist` folder.*
## Credits

- **Download Engine:** [@baconator696](https://github.com/baconator696)
- **GUI & Code:** jorminyo2022

## License

Same as the original project.
