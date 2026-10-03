import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import 'package:image/image.dart' as img;
import 'package:tflite_flutter/tflite_flutter.dart';
import 'package:flutter_tts/flutter_tts.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const KisanPlantDoctorApp());
}

class KisanPlantDoctorApp extends StatelessWidget {
  const KisanPlantDoctorApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Kisan Plant Doctor',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF2E7D32),
          primary: const Color(0xFF2E7D32),
        ),
        useMaterial3: true,
      ),
      home: const HomeScreen(),
    );
  }
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  Interpreter? _interpreter;
  Map<String, dynamic> _classNames = {};
  Map<String, dynamic> _diseaseDb = {};
  final FlutterTts _tts = FlutterTts();
  final ImagePicker _picker = ImagePicker();

  File? _selectedImage;
  bool _isLoading = false;
  List<Map<String, dynamic>> _predictions = [];
  String _selectedLanguage = 'hindi';

  @override
  void initState() {
    super.initState();
    _loadModelAndMetadata();
  }

  Future<void> _loadModelAndMetadata() async {
    setState(() => _isLoading = true);
    try {
      _interpreter = await Interpreter.fromAsset('assets/plant_disease_model.tflite');
      final classNamesStr = await rootBundle.loadString('assets/class_names_allplants.json');
      _classNames = json.decode(classNamesStr);
      final dbStr = await rootBundle.loadString('assets/disease_database.json');
      _diseaseDb = json.decode(dbStr);
    } catch (e) {
      debugPrint("Initialization Error: $e");
    } finally {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _pickImage(ImageSource source) async {
    final pickedFile = await _picker.pickImage(source: source, maxWidth: 1000, maxHeight: 1000);
    if (pickedFile == null) return;

    final file = File(pickedFile.path);
    setState(() {
      _selectedImage = file;
      _predictions = [];
    });

    _classifyImage(file);
  }

  Future<void> _classifyImage(File imageFile) async {
    if (_interpreter == null) return;
    setState(() => _isLoading = true);

    try {
      final bytes = await imageFile.readAsBytes();
      final decodedImage = img.decodeImage(bytes);
      if (decodedImage == null) return;

      final resizedImage = img.copyResize(decodedImage, width: 160, height: 160);

      final input = Float32List(1 * 160 * 160 * 3);
      var bufferIndex = 0;
      for (var y = 0; y < 160; y++) {
        for (var x = 0; x < 160; x++) {
          final pixel = resizedImage.getPixel(x, y);
          input[bufferIndex++] = pixel.r.toDouble();
          input[bufferIndex++] = pixel.g.toDouble();
          input[bufferIndex++] = pixel.b.toDouble();
        }
      }

      final output = List<double>.filled(1 * _classNames.length, 0.0).reshape([1, _classNames.length]);
      _interpreter!.run(input.buffer.asUint8List(), output);

      final List<double> rawProbs = List<double>.from(output[0]);
      final List<Map<String, dynamic>> indexedProbs = [];
      for (int i = 0; i < rawProbs.length; i++) {
        indexedProbs.add({
          'index': i,
          'confidence': rawProbs[i],
          'info': _classNames[i.toString()] ?? {},
        });
      }

      indexedProbs.sort((a, b) => (b['confidence'] as double).compareTo(a['confidence'] as double));

      setState(() {
        _predictions = indexedProbs.take(3).toList();
      });
    } catch (e) {
      debugPrint("Inference Error: $e");
    } finally {
      setState(() => _isLoading = false);
    }
  }

  Map<String, dynamic>? _getDiseaseTreatment(String diseaseName) {
    for (final key in _diseaseDb.keys) {
      if (diseaseName.toLowerCase().contains(key.toLowerCase()) ||
          key.toLowerCase().contains(diseaseName.toLowerCase())) {
        return _diseaseDb[key]?[_selectedLanguage] ?? _diseaseDb[key]?['english'];
      }
    }
    return null;
  }

  Future<void> _speakText(String text) async {
    String langCode = 'hi-IN';
    if (_selectedLanguage == 'marathi') langCode = 'mr-IN';
    if (_selectedLanguage == 'english') langCode = 'en-IN';

    await _tts.setLanguage(langCode);
    await _tts.setPitch(1.0);
    await _tts.setSpeechRate(0.85);
    await _tts.speak(text);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF6F8F5),
      appBar: AppBar(
        title: const Text('🌿 Kisan Plant Doctor', style: TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: const Color(0xFF2E7D32),
        foregroundColor: Colors.white,
        actions: [
          DropdownButtonHideUnderline(
            child: DropdownButton<String>(
              dropdownColor: const Color(0xFF2E7D32),
              value: _selectedLanguage,
              icon: const Icon(Icons.language, color: Colors.white),
              items: const [
                DropdownMenuItem(value: 'hindi', child: Text('हिंदी', style: TextStyle(color: Colors.white))),
                DropdownMenuItem(value: 'marathi', child: Text('मराठी', style: TextStyle(color: Colors.white))),
                DropdownMenuItem(value: 'english', child: Text('English', style: TextStyle(color: Colors.white))),
              ],
              onChanged: (val) {
                if (val != null) setState(() => _selectedLanguage = val);
              },
            ),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF2E7D32)))
          : SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _buildPhotoSelectionArea(),
            const SizedBox(height: 16),
            if (_predictions.isNotEmpty) _buildResultsArea(),
            if (_predictions.isEmpty && _selectedImage == null) _buildFieldTipsArea(),
          ],
        ),
      ),
    );
  }

  Widget _buildPhotoSelectionArea() {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            if (_selectedImage != null)
              ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: Image.file(_selectedImage!, height: 220, width: double.infinity, fit: BoxFit.cover),
              )
            else
              Container(
                height: 180,
                decoration: BoxDecoration(
                  color: Colors.green.shade50,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.green.shade200),
                ),
                child: Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.add_a_photo_outlined, size: 54, color: Colors.green.shade700),
                      const SizedBox(height: 8),
                      Text(
                        _selectedLanguage == 'hindi'
                            ? 'पत्ती की तस्वीर लें'
                            : _selectedLanguage == 'marathi'
                            ? 'पानाचा फोटो काढा'
                            : 'Take photo of diseased leaf',
                        style: TextStyle(color: Colors.green.shade900, fontWeight: FontWeight.w600),
                      ),
                    ],
                  ),
                ),
              ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF2E7D32),
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                    onPressed: () => _pickImage(ImageSource.camera),
                    icon: const Icon(Icons.camera_alt),
                    label: Text(_selectedLanguage == 'hindi' ? 'कैमरा' : _selectedLanguage == 'marathi' ? 'कॅमेरा' : 'Camera'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton.icon(
                    style: OutlinedButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 12)),
                    onPressed: () => _pickImage(ImageSource.gallery),
                    icon: const Icon(Icons.photo_library),
                    label: Text(_selectedLanguage == 'hindi' ? 'गैलरी' : _selectedLanguage == 'marathi' ? 'गॅलरी' : 'Gallery'),
                  ),
                ),
              ],
            )
          ],
        ),
      ),
    );
  }

  Widget _buildResultsArea() {
    final top = _predictions.first;
    final topConf = (top['confidence'] as double) * 100;
    final plant = top['info']['plant'] ?? '';
    final disease = top['info']['disease'] ?? '';
    final treatment = _getDiseaseTreatment(disease);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Card(
          color: topConf > 55 ? const Color(0xFFE8F5E9) : const Color(0xFFFFF3E0),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      '🥇 ${topConf.toStringAsFixed(1)}% Match',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        color: topConf > 55 ? Colors.green.shade800 : Colors.orange.shade900,
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.volume_up, color: Color(0xFF2E7D32)),
                      onPressed: () {
                        if (treatment != null) {
                          final text = "${treatment['name']}. ${treatment['description']}. उपचार: ${treatment['organic']}";
                          _speakText(text);
                        }
                      },
                    ),
                  ],
                ),
                Text(
                  treatment?['name'] ?? '$plant - $disease',
                  style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 4),
                Text(
                  "Severity: ${treatment?['severity'] ?? 'Moderate'}",
                  style: const TextStyle(fontWeight: FontWeight.w600, color: Colors.black54),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        if (treatment != null)
          Card(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildSectionTitle('📋 ' + (_selectedLanguage == 'hindi' ? 'विवरण' : _selectedLanguage == 'marathi' ? 'माहिती' : 'Description')),
                  Text(treatment['description'] ?? '', style: const TextStyle(fontSize: 15)),
                  const Divider(height: 24),
                  _buildSectionTitle('🌿 ' + (_selectedLanguage == 'hindi' ? 'जैविक उपाय' : _selectedLanguage == 'marathi' ? 'सेंद्रिय उपाय' : 'Organic Treatment')),
                  Text(treatment['organic'] ?? '', style: const TextStyle(fontSize: 15)),
                  const Divider(height: 24),
                  _buildSectionTitle('💊 ' + (_selectedLanguage == 'hindi' ? 'रासायनिक उपाय' : _selectedLanguage == 'marathi' ? 'रासायनिक उपाय' : 'Chemical Treatment')),
                  Text(treatment['chemical'] ?? '', style: const TextStyle(fontSize: 15)),
                  const Divider(height: 24),
                  _buildSectionTitle('🛡️ ' + (_selectedLanguage == 'hindi' ? 'रोकथाम' : _selectedLanguage == 'marathi' ? 'प्रतिबंध' : 'Prevention')),
                  Text(treatment['prevention'] ?? '', style: const TextStyle(fontSize: 15)),
                ],
              ),
            ),
          ),
        const SizedBox(height: 12),
        Card(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Top 3 Predictions', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                const SizedBox(height: 8),
                ..._predictions.map((pred) {
                  final conf = (pred['confidence'] as double) * 100;
                  final pName = pred['info']['plant'] ?? '';
                  final dName = pred['info']['disease'] ?? '';
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text('$pName: $dName', style: const TextStyle(fontSize: 14)),
                            Text('${conf.toStringAsFixed(1)}%', style: const TextStyle(fontWeight: FontWeight.bold)),
                          ],
                        ),
                        const SizedBox(height: 4),
                        LinearProgressIndicator(
                          value: conf / 100,
                          color: const Color(0xFF2E7D32),
                          backgroundColor: Colors.grey.shade200,
                        ),
                      ],
                    ),
                  );
                }),
              ],
            ),
          ),
        ),
        const SizedBox(height: 8),
        const Center(
          child: Text(
            '⚠️ Confirm diagnosis with your local agri-expert.',
            style: TextStyle(color: Colors.black54, fontSize: 13),
          ),
        ),
      ],
    );
  }

  Widget _buildSectionTitle(String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6.0),
      child: Text(
        title,
        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF2E7D32)),
      ),
    );
  }

  Widget _buildFieldTipsArea() {
    return Card(
      color: Colors.blueGrey.shade50,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: const [
            Text('📸 Tips for Accurate Diagnosis:', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
            SizedBox(height: 8),
            Text('• Hold camera 15–20 cm away from leaf.'),
            Text('• Keep the sick area inside the frame.'),
            Text('• Avoid harsh sun; prefer shade.'),
            Text('• Hold steady to avoid blur.'),
          ],
        ),
      ),
    );
  }
}