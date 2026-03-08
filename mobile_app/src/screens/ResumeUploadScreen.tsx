import React, { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, ScrollView,
  ActivityIndicator, Alert, Platform,
} from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import { authApi, ResumeAnalysis } from '../services/api';

export default function ResumeUploadScreen({ navigation }: any) {
  const [fileUri, setFileUri] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string>('');
  const [targetRole, setTargetRole] = useState('Product Manager');
  const [targetLocation, setTargetLocation] = useState('Bengaluru');
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<ResumeAnalysis | null>(null);

  async function pickFile() {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: 'application/pdf',
        copyToCacheDirectory: true,
      });
      if (result.canceled) return;
      const asset = result.assets[0];
      setFileUri(asset.uri);
      setFileName(asset.name);
    } catch (e) {
      Alert.alert('Error', 'Could not pick file');
    }
  }

  async function handleUpload() {
    if (!fileUri) {
      Alert.alert('No file', 'Please pick a PDF resume first');
      return;
    }
    setLoading(true);
    try {
      const res = await authApi.uploadResume(fileUri, fileName, targetRole, targetLocation);
      setAnalysis(res.data.analysis);
    } catch (e: any) {
      const msg = e?.response?.data?.detail ?? 'Upload failed';
      Alert.alert('Upload Failed', msg);
    } finally {
      setLoading(false);
    }
  }

  function goHome() {
    navigation.replace('Home');
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <Text style={styles.title}>Upload Your Resume</Text>
      <Text style={styles.sub}>We'll tailor it to every job automatically</Text>

      {/* Target Role */}
      <Text style={styles.label}>Target Role</Text>
      <TextInput
        style={styles.input}
        value={targetRole}
        onChangeText={setTargetRole}
        placeholder="e.g. Product Manager"
        placeholderTextColor="#94a3b8"
      />

      {/* Target Location */}
      <Text style={styles.label}>Target Location</Text>
      <TextInput
        style={styles.input}
        value={targetLocation}
        onChangeText={setTargetLocation}
        placeholder="e.g. Bengaluru"
        placeholderTextColor="#94a3b8"
      />

      {/* File Picker */}
      <TouchableOpacity style={styles.pickBtn} onPress={pickFile}>
        <Text style={styles.pickIcon}>📄</Text>
        <Text style={styles.pickText}>{fileName || 'Choose PDF Resume'}</Text>
      </TouchableOpacity>

      {/* Upload */}
      <TouchableOpacity style={styles.btn} onPress={handleUpload} disabled={loading}>
        {loading
          ? <ActivityIndicator color="#fff" />
          : <Text style={styles.btnText}>Analyse & Upload</Text>}
      </TouchableOpacity>

      {/* Analysis result */}
      {analysis && (
        <View style={styles.analysisCard}>
          <Text style={styles.analysisTitle}>Resume Analysis</Text>

          {!!analysis.summary && (
            <>
              <Text style={styles.sectionHead}>Summary</Text>
              <Text style={styles.bodyText}>{analysis.summary}</Text>
            </>
          )}

          {analysis.strengths?.length > 0 && (
            <>
              <Text style={styles.sectionHead}>Strengths</Text>
              {analysis.strengths.map((s, i) => (
                <Text key={i} style={styles.bullet}>• {s}</Text>
              ))}
            </>
          )}

          {analysis.recommended_roles?.length > 0 && (
            <>
              <Text style={styles.sectionHead}>Recommended Roles</Text>
              <View style={styles.chips}>
                {analysis.recommended_roles.map((r, i) => (
                  <View key={i} style={styles.chip}><Text style={styles.chipText}>{r}</Text></View>
                ))}
              </View>
            </>
          )}

          {analysis.skill_gaps?.length > 0 && (
            <>
              <Text style={styles.sectionHead}>Skill Gaps</Text>
              {analysis.skill_gaps.map((s, i) => (
                <Text key={i} style={styles.bullet}>• {s}</Text>
              ))}
            </>
          )}

          {analysis.suggested_keywords?.length > 0 && (
            <>
              <Text style={styles.sectionHead}>Keywords to Add</Text>
              <View style={styles.chips}>
                {analysis.suggested_keywords.map((k, i) => (
                  <View key={i} style={[styles.chip, styles.chipGreen]}>
                    <Text style={[styles.chipText, styles.chipTextGreen]}>{k}</Text>
                  </View>
                ))}
              </View>
            </>
          )}

          <TouchableOpacity style={styles.doneBtn} onPress={goHome}>
            <Text style={styles.btnText}>Start Finding Jobs</Text>
          </TouchableOpacity>
        </View>
      )}

      {!analysis && (
        <TouchableOpacity onPress={goHome} style={styles.skipLink}>
          <Text style={styles.skipText}>Skip for now</Text>
        </TouchableOpacity>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f1f5f9' },
  content: { padding: 24, paddingBottom: 48 },
  title: { fontSize: 24, fontWeight: '800', color: '#0f172a', marginBottom: 4 },
  sub: { fontSize: 14, color: '#64748b', marginBottom: 24 },
  label: { fontSize: 13, fontWeight: '600', color: '#374151', marginBottom: 4 },
  input: {
    borderWidth: 1, borderColor: '#e2e8f0', borderRadius: 10,
    padding: 12, fontSize: 15, color: '#0f172a', marginBottom: 14, backgroundColor: '#fff',
  },
  pickBtn: {
    borderWidth: 2, borderColor: '#2563eb', borderStyle: 'dashed', borderRadius: 12,
    padding: 18, alignItems: 'center', marginBottom: 16, backgroundColor: '#eff6ff',
  },
  pickIcon: { fontSize: 32, marginBottom: 6 },
  pickText: { color: '#2563eb', fontWeight: '600', fontSize: 14 },
  btn: {
    backgroundColor: '#2563eb', borderRadius: 10, padding: 14,
    alignItems: 'center', marginBottom: 24,
  },
  btnText: { color: '#fff', fontSize: 15, fontWeight: '700' },
  analysisCard: {
    backgroundColor: '#fff', borderRadius: 14, padding: 20,
    shadowColor: '#000', shadowOpacity: 0.06, shadowRadius: 10, elevation: 3,
    marginBottom: 12,
  },
  analysisTitle: { fontSize: 18, fontWeight: '800', color: '#0f172a', marginBottom: 14 },
  sectionHead: { fontSize: 13, fontWeight: '700', color: '#2563eb', marginTop: 12, marginBottom: 4 },
  bodyText: { fontSize: 14, color: '#374151', lineHeight: 20 },
  bullet: { fontSize: 14, color: '#374151', marginBottom: 2 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 4 },
  chip: {
    backgroundColor: '#dbeafe', borderRadius: 20, paddingHorizontal: 10, paddingVertical: 4,
  },
  chipText: { fontSize: 12, color: '#1d4ed8', fontWeight: '600' },
  chipGreen: { backgroundColor: '#dcfce7' },
  chipTextGreen: { color: '#15803d' },
  doneBtn: {
    backgroundColor: '#16a34a', borderRadius: 10, padding: 14,
    alignItems: 'center', marginTop: 20,
  },
  skipLink: { alignItems: 'center', marginTop: 8 },
  skipText: { color: '#94a3b8', fontSize: 14 },
});
