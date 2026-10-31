import 'package:flutter/material.dart';
import 'package:window_manager/window_manager.dart';
import 'package:avatar_glow/avatar_glow.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await windowManager.ensureInitialized();

  WindowOptions windowOptions = const WindowOptions(
    size: Size(320, 450), 
    alwaysOnTop: true,
    titleBarStyle: TitleBarStyle.hidden,
    backgroundColor: Colors.transparent,
  );

  windowManager.waitUntilReadyToShow(windowOptions, () async {
    await windowManager.show();
    await windowManager.focus();
    await windowManager.setAlignment(Alignment.bottomRight); 
  });

  runApp(const VoiceBotApp());
}

class VoiceBotApp extends StatelessWidget {
  const VoiceBotApp({super.key});

  @override
  Widget build(BuildContext context) {
    return const MaterialApp(
      debugShowCheckedModeBanner: false,
      home: HoverBotUI(),
    );
  }
}

class HoverBotUI extends StatefulWidget {
  const HoverBotUI({super.key});

  @override
  State<HoverBotUI> createState() => _HoverBotUIState();
}

class _HoverBotUIState extends State<HoverBotUI> {
  bool _isListening = false;
  String _displayText = "Ready to scan for vulnerabilities.";
  late stt.SpeechToText _speech;
  bool _isSpeechInitialized = false;

  @override
  void initState() {
    super.initState();
    _speech = stt.SpeechToText();
    _initSpeech();
  }

  void _initSpeech() async {
    _isSpeechInitialized = await _speech.initialize(
      onError: (error) => setState(() => _displayText = "Speech Error: ${error.errorMsg}"),
    );
    setState(() {});
  }

  void _toggleListening() async {
    if (!_isSpeechInitialized) {
      setState(() => _displayText = "Speech engine not available.");
      return;
    }

    if (!_isListening) {
      setState(() {
        _isListening = true;
        _displayText = "Listening...";
      });
      await _speech.listen(
        onResult: (result) {
          setState(() {
            _displayText = result.recognizedWords;
          });
        },
      );
    } else {
      setState(() {
        _isListening = false;
      });
      await _speech.stop();
      
      // The final spoken text is now saved in _displayText.
      // Call Person 2's Python backend API here and pass _displayText to it.
      setState(() {
        _displayText = "Sending '$_displayText' to Gemma 4...";
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF1E1E1E), 
      body: DragToMoveArea(
        child: Column(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(vertical: 12),
              width: double.infinity,
              color: const Color(0xFF2D2D2D),
              child: const Text(
                "AI Security Scanner",
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.white70, fontWeight: FontWeight.bold),
              ),
            ),
            
            Expanded(
              child: Center(
                child: Container(
                  margin: const EdgeInsets.all(16),
                  padding: const EdgeInsets.all(16),
                  width: double.infinity,
                  decoration: BoxDecoration(
                    color: const Color(0xFF252526),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.white12),
                  ),
                  child: SingleChildScrollView(
                    child: Text(
                      _displayText,
                      style: const TextStyle(color: Colors.white, fontSize: 14, height: 1.5),
                      textAlign: TextAlign.center,
                    ),
                  ),
                ),
              ),
            ),

            Padding(
              padding: const EdgeInsets.only(bottom: 20),
              child: AvatarGlow(
                animate: _isListening,
                glowColor: Colors.blueAccent,
                duration: const Duration(milliseconds: 2000),
                repeat: true,
                child: GestureDetector(
                  onTap: _toggleListening,
                  child: CircleAvatar(
                    backgroundColor: _isListening ? Colors.blueAccent : const Color(0xFF333333),
                    radius: 35,
                    child: Icon(
                      _isListening ? Icons.mic : Icons.mic_none,
                      color: Colors.white,
                      size: 30,
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}