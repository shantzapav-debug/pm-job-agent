import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import React, { useEffect, useState } from 'react';
import { ActivityIndicator, View, StatusBar } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

import HomeScreen from './src/screens/HomeScreen';
import JobDetailScreen from './src/screens/JobDetailScreen';
import ResumeDiffScreen from './src/screens/ResumeDiffScreen';
import LoginScreen from './src/screens/LoginScreen';
import SignupScreen from './src/screens/SignupScreen';
import ResumeUploadScreen from './src/screens/ResumeUploadScreen';

const Stack = createNativeStackNavigator();

export default function App() {
  const [initialRoute, setInitialRoute] = useState<string | null>(null);

  useEffect(() => {
    AsyncStorage.getItem('auth_token').then((token) => {
      setInitialRoute(token ? 'Home' : 'Login');
    });
  }, []);

  if (!initialRoute) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#f1f5f9' }}>
        <ActivityIndicator size="large" color="#2563eb" />
      </View>
    );
  }

  return (
    <NavigationContainer>
      <StatusBar barStyle="dark-content" backgroundColor="#fff" />
      <Stack.Navigator
        initialRouteName={initialRoute}
        screenOptions={{
          headerStyle: { backgroundColor: '#fff' },
          headerTintColor: '#0f172a',
          headerShadowVisible: true,
          headerTitleStyle: { fontWeight: '700' },
        }}
      >
        {/* Auth screens */}
        <Stack.Screen name="Login" component={LoginScreen} options={{ headerShown: false }} />
        <Stack.Screen name="Signup" component={SignupScreen} options={{ headerShown: false }} />
        <Stack.Screen name="ResumeUpload" component={ResumeUploadScreen} options={{ title: 'Resume Setup' }} />

        {/* Main app screens */}
        <Stack.Screen name="Home" component={HomeScreen} options={{ title: 'PM Job Agent', headerShown: false }} />
        <Stack.Screen name="JobDetail" component={JobDetailScreen} options={{ title: 'Job Detail' }} />
        <Stack.Screen name="ResumeDiff" component={ResumeDiffScreen} options={{ title: 'Resume Changes' }} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
