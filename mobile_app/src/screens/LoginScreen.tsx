import React, { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  KeyboardAvoidingView, Platform, ActivityIndicator, Alert,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { authApi } from '../services/api';

export default function LoginScreen({ navigation }: any) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleLogin() {
    if (!email.trim() || !password) {
      Alert.alert('Error', 'Enter email and password');
      return;
    }
    setLoading(true);
    try {
      const res = await authApi.login(email.trim().toLowerCase(), password);
      await AsyncStorage.setItem('auth_token', res.data.token);
      await AsyncStorage.setItem('auth_user', JSON.stringify(res.data.user));
      if (!res.data.user.has_resume) {
        navigation.replace('ResumeUpload');
      } else {
        navigation.replace('Home');
      }
    } catch (e: any) {
      const msg = e?.response?.data?.detail ?? 'Login failed';
      Alert.alert('Login Failed', msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <View style={styles.card}>
        <Text style={styles.title}>PM Job Agent</Text>
        <Text style={styles.sub}>Sign in to your account</Text>

        <TextInput
          style={styles.input}
          placeholder="Email"
          placeholderTextColor="#94a3b8"
          autoCapitalize="none"
          keyboardType="email-address"
          value={email}
          onChangeText={setEmail}
        />
        <TextInput
          style={styles.input}
          placeholder="Password"
          placeholderTextColor="#94a3b8"
          secureTextEntry
          value={password}
          onChangeText={setPassword}
          onSubmitEditing={handleLogin}
        />

        <TouchableOpacity style={styles.btn} onPress={handleLogin} disabled={loading}>
          {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.btnText}>Sign In</Text>}
        </TouchableOpacity>

        <TouchableOpacity onPress={() => navigation.navigate('Signup')} style={styles.link}>
          <Text style={styles.linkText}>No account? <Text style={styles.linkBold}>Sign up</Text></Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f1f5f9', justifyContent: 'center', padding: 24 },
  card: {
    backgroundColor: '#fff', borderRadius: 16, padding: 28,
    shadowColor: '#000', shadowOpacity: 0.08, shadowRadius: 12, elevation: 4,
  },
  title: { fontSize: 26, fontWeight: '800', color: '#0f172a', textAlign: 'center', marginBottom: 4 },
  sub: { fontSize: 14, color: '#64748b', textAlign: 'center', marginBottom: 24 },
  input: {
    borderWidth: 1, borderColor: '#e2e8f0', borderRadius: 10,
    padding: 13, fontSize: 15, color: '#0f172a', marginBottom: 12,
  },
  btn: {
    backgroundColor: '#2563eb', borderRadius: 10, padding: 14,
    alignItems: 'center', marginTop: 4,
  },
  btnText: { color: '#fff', fontSize: 15, fontWeight: '700' },
  link: { marginTop: 18, alignItems: 'center' },
  linkText: { fontSize: 14, color: '#64748b' },
  linkBold: { color: '#2563eb', fontWeight: '700' },
});
