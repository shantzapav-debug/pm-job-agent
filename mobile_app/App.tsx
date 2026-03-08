import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import React from 'react';
import { StatusBar } from 'react-native';
import HomeScreen from './src/screens/HomeScreen';
import JobDetailScreen from './src/screens/JobDetailScreen';
import ResumeDiffScreen from './src/screens/ResumeDiffScreen';

const Stack = createNativeStackNavigator();

export default function App() {
  return (
    <NavigationContainer>
      <StatusBar barStyle="dark-content" backgroundColor="#fff" />
      <Stack.Navigator
        screenOptions={{
          headerStyle: { backgroundColor: '#fff' },
          headerTintColor: '#0f172a',
          headerShadowVisible: true,
          headerTitleStyle: { fontWeight: '700' },
        }}
      >
        <Stack.Screen
          name="Home"
          component={HomeScreen}
          options={{ title: 'PM Job Agent', headerShown: false }}
        />
        <Stack.Screen
          name="JobDetail"
          component={JobDetailScreen}
          options={{ title: 'Job Detail' }}
        />
        <Stack.Screen
          name="ResumeDiff"
          component={ResumeDiffScreen}
          options={{ title: 'Resume Changes' }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
