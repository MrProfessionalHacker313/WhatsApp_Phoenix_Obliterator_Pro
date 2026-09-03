import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, TextInput, ScrollView, Alert, Share, Platform,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useTheme } from '../context/ThemeContext';
import api from '../services/api';

const LICENSE_KEY_KEY = '@eagle_license_key';
const PROXY_KEY = '@eagle_proxy';
const THEME_KEY = '@eagle_theme';

const THEMES = [
  { key: 'dark', label: 'DARK', colors: { primary: '#0f172a', secondary: '#1e293b', accent: '#FFD700' } },
  { key: 'golden', label: 'GOLDEN', colors: { primary: '#B8860B', secondary: '#DAA520', accent: '#FFD700' } },
  { key: 'red', label: 'RED', colors: { primary: '#7F1D1D', secondary: '#991B1B', accent: '#EF4444' } },
];

export default function SettingsScreen({ navigation }) {
  const { theme } = useTheme();
  const [licenseKey, setLicenseKey] = useState('');
  const [proxy, setProxy] = useState('');
  const [currentTheme, setCurrentTheme] = useState('dark');
  const [isActivating, setIsActivating] = useState(false);
  const [licenseStatus, setLicenseStatus] = useState(null);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const storedLicense = await AsyncStorage.getItem(LICENSE_KEY_KEY);
      if (storedLicense) setLicenseKey(storedLicense);

      const storedProxy = await AsyncStorage.getItem(PROXY_KEY);
      if (storedProxy) setProxy(storedProxy);

      const storedTheme = await AsyncStorage.getItem(THEME_KEY);
      if (storedTheme) setCurrentTheme(storedTheme);
    } catch (error) {
      console.log('Settings load error:', error);
    }
  };

  const activateLicense = async () => {
    if (!licenseKey.trim()) {
      Alert.alert('Error', 'Please enter a license key');
      return;
    }

    setIsActivating(true);
    try {
      const response = await api.verifyLicense(licenseKey);
      if (response.valid) {
        await AsyncStorage.setItem(LICENSE_KEY_KEY, licenseKey);
        setLicenseStatus({
          valid: true,
          tier: response.tier,
          expiresAt: response.expires_at,
        });
        Alert.alert('Success', `License activated! Tier: ${response.tier}`);
      } else {
        Alert.alert('Invalid License', response.reason || 'The license key is invalid');
      }
    } catch (error) {
      Alert.alert('Error', error.message);
    } finally {
      setIsActivating(false);
    }
  };

  const saveProxy = async () => {
    try {
      await AsyncStorage.setItem(PROXY_KEY, proxy);
      Alert.alert('Success', 'Proxy settings saved');
    } catch (error) {
      Alert.alert('Error', 'Failed to save proxy settings');
    }
  };

  const changeTheme = async (themeKey) => {
    try {
      await AsyncStorage.setItem(THEME_KEY, themeKey);
      setCurrentTheme(themeKey);
      Alert.alert('Theme Changed', `Theme set to ${themeKey.toUpperCase()}`);
    } catch (error) {
      Alert.alert('Error', 'Failed to change theme');
    }
  };

  const exportData = async () => {
    try {
      const data = {
        licenseKey,
        proxy,
        theme: currentTheme,
        exportedAt: new Date().toISOString(),
        appVersion: '3.0.0',
      };

      const jsonString = JSON.stringify(data, null, 2);
      await Share.share({
        title: 'Eagle App Data Export',
        message: jsonString,
      });
    } catch (error) {
      if (error.message !== 'User did not share') {
        Alert.alert('Error', 'Failed to export data');
      }
    }
  };

  const deactivateLicense = async () => {
    Alert.alert(
      'Deactivate License',
      'Are you sure you want to deactivate your license?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Deactivate',
          style: 'destructive',
          onPress: async () => {
            try {
              await AsyncStorage.removeItem(LICENSE_KEY_KEY);
              setLicenseKey('');
              setLicenseStatus(null);
              Alert.alert('Success', 'License deactivated');
            } catch (error) {
              Alert.alert('Error', 'Failed to deactivate license');
            }
          },
        },
      ]
    );
  };

  const logout = async () => {
    Alert.alert(
      'Logout',
      'Are you sure you want to logout? This will clear all local data.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Logout',
          style: 'destructive',
          onPress: async () => {
            try {
              await AsyncStorage.clear();
              Alert.alert('Success', 'Logged out successfully. Restart the app.');
            } catch (error) {
              Alert.alert('Error', 'Failed to logout');
            }
          },
        },
      ]
    );
  };

  const currentThemeColors = THEMES.find(t => t.key === currentTheme)?.colors || THEMES[0].colors;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>⚙️ SETTINGS</Text>
        <Text style={styles.headerSubtitle}>Eagle Configuration</Text>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>🔐 LICENSE</Text>
        <View style={[styles.card, { borderColor: theme.gold }]}>
          <TextInput
            style={[styles.input, { borderColor: theme.darkGold }]}
            value={licenseKey}
            onChangeText={setLicenseKey}
            placeholder="Enter license key"
            placeholderTextColor={theme.muted}
            autoCapitalize="none"
          />
          <TouchableOpacity
            style={[styles.button, { backgroundColor: theme.gold }]}
            onPress={activateLicense}
            disabled={isActivating}>
            <Text style={styles.buttonText}>
              {isActivating ? 'ACTIVATING...' : 'ACTIVATE LICENSE'}
            </Text>
          </TouchableOpacity>

          {licenseStatus && (
            <View style={[styles.statusBadge, { backgroundColor: '#22C55E20', borderColor: '#22C55E' }]}>
              <Text style={[styles.statusBadgeText, { color: '#22C55E' }]}>
                ✓ ACTIVE - {licenseStatus.tier?.toUpperCase()}
              </Text>
            </View>
          )}
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>🌐 PROXY</Text>
        <View style={[styles.card, { borderColor: theme.steel }]}>
          <TextInput
            style={[styles.input, { borderColor: theme.darkGold }]}
            value={proxy}
            onChangeText={setProxy}
            placeholder="http://proxy:port"
            placeholderTextColor={theme.muted}
            autoCapitalize="none"
          />
          <TouchableOpacity
            style={[styles.button, { backgroundColor: theme.steel }]}
            onPress={saveProxy}>
            <Text style={styles.buttonText}>SAVE PROXY</Text>
          </TouchableOpacity>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>🎨 THEME</Text>
        <View style={[styles.card, { borderColor: currentThemeColors.accent }]}>
          {THEMES.map((theme) => (
            <TouchableOpacity
              key={theme.key}
              style={[
                styles.themeOption,
                {
                  backgroundColor: currentTheme === theme.key ? theme.colors.accent + '30' : 'transparent',
                  borderColor: theme.colors.accent,
                },
              ]}
              onPress={() => changeTheme(theme.key)}>
              <View style={[styles.themePreview, { backgroundColor: theme.colors.primary }]} />
              <Text style={[styles.themeLabel, { color: theme.colors.accent }]}>
                {theme.label}
              </Text>
              {currentTheme === theme.key && (
                <Text style={styles.themeCheck}>✓</Text>
              )}
            </TouchableOpacity>
          ))}
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>📤 DATA</Text>
        <View style={[styles.card, { borderColor: theme.gold }]}>
          <TouchableOpacity style={styles.actionRow} onPress={exportData}>
            <Text style={styles.actionIcon}>📤</Text>
            <Text style={styles.actionLabel}>Export Data</Text>
            <Text style={styles.actionArrow}>›</Text>
          </TouchableOpacity>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>ℹ️ ABOUT</Text>
        <View style={[styles.card, { borderColor: theme.muted }]}>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Version</Text>
            <Text style={styles.infoValue}>3.0.0 Ultimate</Text>
          </View>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Build</Text>
            <Text style={styles.infoValue}>2026.09.02</Text>
          </View>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Platform</Text>
            <Text style={styles.infoValue}>{Platform.OS}</Text>
          </View>
        </View>
      </View>

      <View style={styles.section}>
        <TouchableOpacity style={[styles.dangerButton, { borderColor: theme.fire }]} onPress={deactivateLicense}>
          <Text style={[styles.dangerButtonText, { color: theme.fire }]}>🔓 DEACTIVATE LICENSE</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.dangerButton, { borderColor: theme.fire }]} onPress={logout}>
          <Text style={[styles.dangerButtonText, { color: theme.fire }]}>🚪 LOGOUT</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.footer}>
        <Text style={styles.footerText}>🦅 PHOENIX EAGLE v3.0</Text>
        <Text style={styles.footerSubtext}>Phoenix Security Labs</Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.dark,
  },
  content: {
    padding: 16,
    paddingBottom: 40,
  },
  header: {
    alignItems: 'center',
    marginBottom: 24,
    paddingVertical: 16,
    borderBottomWidth: 2,
    borderBottomColor: theme.gold,
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: 'bold',
    color: theme.gold,
    letterSpacing: 2,
  },
  headerSubtitle: {
    fontSize: 14,
    color: theme.muted,
    marginTop: 4,
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: theme.gold,
    marginBottom: 12,
    letterSpacing: 1,
  },
  card: {
    backgroundColor: theme.card,
    borderRadius: 16,
    padding: 16,
    borderWidth: 2,
    gap: 12,
  },
  input: {
    height: 48,
    backgroundColor: theme.darker,
    borderRadius: 12,
    paddingHorizontal: 16,
    color: theme.text,
    fontSize: 14,
    borderWidth: 1,
  },
  button: {
    height: 48,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  buttonText: {
    color: theme.dark,
    fontSize: 14,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  statusBadge: {
    padding: 12,
    borderRadius: 10,
    alignItems: 'center',
    borderWidth: 1,
  },
  statusBadgeText: {
    fontSize: 14,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  themeOption: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    padding: 14,
    borderRadius: 12,
    borderWidth: 1.5,
    marginBottom: 8,
  },
  themePreview: {
    width: 32,
    height: 32,
    borderRadius: 8,
  },
  themeLabel: {
    flex: 1,
    fontSize: 14,
    fontWeight: '600',
    letterSpacing: 1,
  },
  themeCheck: {
    fontSize: 18,
    fontWeight: 'bold',
    color: theme.gold,
  },
  actionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 4,
  },
  actionIcon: {
    fontSize: 24,
  },
  actionLabel: {
    flex: 1,
    fontSize: 16,
    color: theme.text,
    fontWeight: '500',
  },
  actionArrow: {
    fontSize: 24,
    color: theme.muted,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
  },
  infoLabel: {
    fontSize: 14,
    color: theme.muted,
    fontWeight: '500',
  },
  infoValue: {
    fontSize: 14,
    color: theme.text,
    fontWeight: '600',
  },
  dangerButton: {
    padding: 16,
    borderRadius: 12,
    alignItems: 'center',
    borderWidth: 1.5,
    marginBottom: 12,
    backgroundColor: 'transparent',
  },
  dangerButtonText: {
    fontSize: 14,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  footer: {
    alignItems: 'center',
    paddingVertical: 20,
    marginTop: 20,
    borderTopWidth: 1,
    borderTopColor: theme.darkGold + '40',
  },
  footerText: {
    fontSize: 16,
    color: theme.gold,
    fontWeight: 'bold',
    letterSpacing: 2,
  },
  footerSubtext: {
    fontSize: 12,
    color: theme.muted,
    marginTop: 4,
  },
});
