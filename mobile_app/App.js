import React, { useState, useRef, useEffect } from 'react';
import { View, Text, StyleSheet, Animated, Dimensions, StatusBar } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { StripeProvider } from '@stripe/stripe-react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import SplashScreen from 'react-native-splash-screen';
import { ThemeProvider, useTheme } from './src/context/ThemeContext';
import HomeScreen from './src/screens/HomeScreen';
import OperationsScreen from './src/screens/OperationsScreen';
import HistoryScreen from './src/screens/HistoryScreen';
import PremiumScreen from './src/screens/PremiumScreen';
import SettingsScreen from './src/screens/SettingsScreen';

const Tab = createBottomTabNavigator();

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');

const EagleSplashScreen = ({ onFinish }) => {
  const eagleOpacity = useRef(new Animated.Value(0)).current;
  const eagleScale = useRef(new Animated.Value(0.5)).current;
  const featherRotate = useRef(new Animated.Value(0)).current;
  const fadeOut = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    const animateSplash = () => {
      Animated.sequence([
        Animated.parallel([
          Animated.timing(eagleOpacity, {
            toValue: 1,
            duration: 800,
            useNativeDriver: true,
          }),
          Animated.spring(eagleScale, {
            toValue: 1,
            friction: 4,
            tension: 40,
            useNativeDriver: true,
          }),
        ]),
        Animated.timing(featherRotate, {
          toValue: 1,
          duration: 1500,
          useNativeDriver: true,
        }),
        Animated.timing(fadeOut, {
          toValue: 0,
          duration: 600,
          delay: 800,
          useNativeDriver: true,
        }),
      ]).start(() => {
        onFinish();
      });
    };

    animateSplash();
  }, []);

  const spin = featherRotate.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '360deg'],
  });

  return (
    <Animated.View style={[styles.splashContainer, { opacity: fadeOut }]}>
      <StatusBar hidden />
      <View style={styles.splashBackground}>
        <View style={styles.featherPattern}>
          {[...Array(8)].map((_, i) => (
            <Animated.View
              key={i}
              style={[
                styles.feather,
                {
                  left: `${10 + i * 12}%`,
                  top: `${20 + (i % 3) * 25}%`,
                  transform: [{ rotate: spin }],
                  opacity: 0.3 + (i % 3) * 0.2,
                },
              ]}
            />
          ))}
        </View>

        <Animated.View
          style={[
            styles.eagleLogoContainer,
            {
              opacity: eagleOpacity,
              transform: [{ scale: eagleScale }],
            },
          ]}>
          <Text style={styles.eagleEmoji}>🦅</Text>
          <Text style={styles.eagleTitle}>PHOENIX EAGLE</Text>
          <Text style={styles.eagleSubtitle}>OBLITERATOR PRO</Text>
          <View style={styles.eagleDivider} />
          <Text style={styles.eagleLoading}>
            <Animated.Text style={{ transform: [{ rotate: spin }] }}>⚡</Animated.Text>
            {' '}INITIALIZING EAGLE EYE{'\n'}
            <Animated.Text style={{ transform: [{ rotate: spin }] }}>🔥</Animated.Text>
            {' '}LOADING OPERATIONS MODULE
          </Text>
        </Animated.View>
      </View>
    </Animated.View>
  );
};

const AppContent = () => {
  const { theme } = useTheme();

  return (
    <NavigationContainer>
      <Tab.Navigator
        screenOptions={({ route }) => ({
          tabBarIcon: ({ focused, color, size }) => {
            let icon = '';
            switch (route.name) {
              case 'Home': icon = '🦅'; break;
              case 'Operations': icon = '⚡'; break;
              case 'History': icon = '📊'; break;
              case 'Premium': icon = '💰'; break;
              case 'Settings': icon = '⚙️'; break;
            }
            return <Text style={{ fontSize: size + 4 }}>{icon}</Text>;
          },
          tabBarActiveTintColor: theme.gold,
          tabBarInactiveTintColor: theme.muted,
          tabBarStyle: {
            backgroundColor: theme.darker,
            borderTopColor: theme.darkGold,
            borderTopWidth: 2,
            paddingTop: 8,
            height: 70,
          },
          headerStyle: {
            backgroundColor: theme.darkGold,
            borderBottomWidth: 2,
            borderBottomColor: theme.gold,
          },
          headerTintColor: theme.gold,
          headerTitleStyle: {
            fontWeight: 'bold',
            fontSize: 18,
          },
        })}>
        <Tab.Screen 
          name="Home" 
          component={HomeScreen}
          options={{ 
            tabBarLabel: 'Home',
            headerTitle: <Text style={{ color: theme.gold, fontWeight: 'bold' }}>🦅 Home</Text>
          }}
        />
        <Tab.Screen 
          name="Operations" 
          component={OperationsScreen}
          options={{ 
            tabBarLabel: 'Operations',
            headerTitle: <Text style={{ color: theme.gold, fontWeight: 'bold' }}>⚡ Operations</Text>
          }}
        />
        <Tab.Screen 
          name="History" 
          component={HistoryScreen}
          options={{ 
            tabBarLabel: 'History',
            headerTitle: <Text style={{ color: theme.gold, fontWeight: 'bold' }}>📊 History</Text>
          }}
        />
        <Tab.Screen 
          name="Premium" 
          component={PremiumScreen}
          options={{ 
            tabBarLabel: 'Premium',
            headerTitle: <Text style={{ color: theme.gold, fontWeight: 'bold' }}>💰 Premium</Text>
          }}
        />
        <Tab.Screen 
          name="Settings" 
          component={SettingsScreen}
          options={{ 
            tabBarLabel: 'Settings',
            headerTitle: <Text style={{ color: theme.gold, fontWeight: 'bold' }}>⚙️ Settings</Text>
          }}
        />
      </Tab.Navigator>
    </NavigationContainer>
  );
};

export default function App() {
  const [showSplash, setShowSplash] = useState(true);

  useEffect(() => {
    const init = async () => {
      await new Promise(resolve => setTimeout(resolve, 100));
      SplashScreen.hide();
    };
    init();
  }, []);

  if (showSplash) {
    return <EagleSplashScreen onFinish={() => setShowSplash(false)} />;
  }

  return (
    <SafeAreaProvider>
      <ThemeProvider>
        <StripeProvider publishableKey="pk_test_your_publishable_key_here">
          <StatusBar barStyle="light-content" backgroundColor="#020617" />
          <AppContent />
        </StripeProvider>
      </ThemeProvider>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  splashContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  splashBackground: {
    flex: 1,
    width: SCREEN_WIDTH,
    height: SCREEN_HEIGHT,
    backgroundColor: '#020617',
    justifyContent: 'center',
    alignItems: 'center',
    position: 'relative',
  },
  featherPattern: {
    position: 'absolute',
    width: '100%',
    height: '100%',
  },
  feather: {
    position: 'absolute',
    width: 30,
    height: 60,
    backgroundColor: '#FFD700',
    borderRadius: 15,
    opacity: 0.3,
  },
  eagleLogoContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 40,
  },
  eagleEmoji: {
    fontSize: 100,
    marginBottom: 20,
  },
  eagleTitle: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#FFD700',
    textAlign: 'center',
    letterSpacing: 3,
    textShadowColor: '#B8860B',
    textShadowOffset: { width: 2, height: 2 },
    textShadowRadius: 8,
  },
  eagleSubtitle: {
    fontSize: 18,
    color: '#DC2626',
    marginTop: 8,
    fontWeight: '600',
    letterSpacing: 2,
  },
  eagleDivider: {
    width: 200,
    height: 3,
    backgroundColor: '#FFD700',
    marginVertical: 20,
    borderRadius: 2,
  },
  eagleLoading: {
    fontSize: 14,
    color: '#94a3b8',
    textAlign: 'center',
    lineHeight: 24,
  },
});
