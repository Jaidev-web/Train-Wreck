import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter/material.dart';
import 'package:window_manager/window_manager.dart';
import 'package:avatar_glow/avatar_glow.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await windowManager.ensureInitialized();

  WindowOptions windowOptions = const WindowOptions(
    size: Size(80, 80), 
    alwaysOnTop: true,
    titleBarStyle: TitleBarStyle.hidden,
    backgroundColor: Colors.transparent,
    skipTaskbar: true, 
  );

  windowManager.waitUntilReadyToShow(windowOptions, () async {
    await windowManager.setAsFrameless();
    await windowManager.setHasShadow(false);
    await windowManager.show();
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
  bool _isProcessing = false;
  bool _isExpanded = false;
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

  void _toggleWindowSize() async {
    _isExpanded = !_isExpanded;
    if (_isExpanded) {
      await windowManager.setSize(const Size(320, 450));
    } else {
      await windowManager.setSize(const Size(80, 80));
    }
    await windowManager.setAlignment(Alignment.bottomRight);
    setState(() {});
  }

  void _startListening() async {
    if (!_isSpeechInitialized) return;
    
    if (!_isExpanded) _toggleWindowSize();

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
  }

  void _stopListening() async {
    setState(() {
      _isListening = false;
      _isProcessing = true;
      _displayText = "Sending to Gemma 4...";
    });
    await _speech.stop();
    
    // -> THIS WAS MISSING: Actually triggers the FastAPI backend call!
    await _scanLocalRepo();
  }

  Future<void> _scanLocalRepo() async {
    final url = Uri.parse('http://127.0.0.1:8000/scan-repo');
    
    try {
      final response = await http.post(
        url,
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({
          "repo_folder_path": "C:\\Users\\Dikshita\\Desktop\\Train Wreck\\test_folder" 
        }),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        
        if (data['status'] == 'safe' || data['status'] == 'error') {
          setState(() => _displayText = data['message']);
        } else if (data['status'] == 'scan_complete') {
          List reports = data['report'];
          String finalOutput = "Scanned ${data['total_files_scanned']} files:\n\n";
          
          for (var item in reports) {
            var analysis = item['ai_analysis'];
            String action = (analysis['action'] ?? 'UNKNOWN').toString().toUpperCase();
            String reason = analysis['reason'] ?? '';
            
            finalOutput += "📁 ${item['file']} ➔ [$action]\n";
            if (reason.isNotEmpty) {
              finalOutput += "Reason: $reason\n";
            }
            finalOutput += "\n";
          }
          setState(() => _displayText = finalOutput);
        }
      } else {
        setState(() => _displayText = "Backend Error: ${response.statusCode}");
      }
    } catch (e) {
      setState(() => _displayText = "Connection failed:\n$e");
    } finally {
      setState(() => _isProcessing = false); 
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!_isExpanded) {
      bool isActive = _isListening || _isProcessing;
      Color ringColor = _isListening ? Colors.blueAccent : Colors.purpleAccent;

      return Scaffold(
        backgroundColor: Colors.transparent,
        body: DragToMoveArea(
          child: Center(
            child: GestureDetector(
              onTap: _toggleWindowSize,
              child: AvatarGlow(
                animate: isActive,
                glowColor: ringColor,
                duration: const Duration(milliseconds: 1500),
                repeat: true,
                child: Container(
                  width: 70,
                  height: 70,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: isActive ? ringColor : Colors.transparent,
                      width: isActive ? 3.0 : 0.0,
                    ),
                    boxShadow: [
                      if (isActive)
                        BoxShadow(
                          color: ringColor.withOpacity(0.6),
                          blurRadius: 15,
                          spreadRadius: 3,
                        )
                      else
                        BoxShadow(
                          color: Colors.black.withOpacity(0.5),
                          blurRadius: 8,
                          offset: const Offset(0, 4),
                        ),
                    ],
                    image: const DecorationImage(
                      image: AssetImage('assets/bot_icon.png'), 
                      fit: BoxFit.cover,
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      );
    }

    return Scaffold(
      backgroundColor: const Color(0xFF1E1E1E), 
      body: DragToMoveArea(
        child: Column(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 12),
              color: const Color(0xFF2D2D2D),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    "AI Security Scanner",
                    style: TextStyle(color: Colors.white70, fontWeight: FontWeight.bold),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close_fullscreen, color: Colors.white54, size: 18),
                    onPressed: _toggleWindowSize, 
                  )
                ],
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
                  onTapDown: (_) => _startListening(),
                  onTapUp: (_) => _stopListening(),
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