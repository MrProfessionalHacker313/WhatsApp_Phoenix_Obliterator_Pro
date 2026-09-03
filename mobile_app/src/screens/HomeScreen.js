import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, TextInput, ScrollView, Animated, Dimensions,
} from 'react-native';
import { useTheme } from '../context/ThemeContext';
import api from '../services/api';
import { addToHistory } from '../services/history';

export default function HomeScreen({ navigation }) {
  const { theme } = useTheme();
  const [totalOps, setTotalOps] = useState(0);
  const [successRate, setSuccessRate] = useState(0);
  const [countryCode, setCountryCode] = useState('+1');
  const [countryFlag, setCountryFlag] = useState('🇺🇸');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [logs, setLogs] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showCountryPicker, setShowCountryPicker] = useState(false);
  const successAnim = useRef(new Animated.Value(0)).current;
  const scrollViewRef = useRef(null);

  const COUNTRIES = [
    { code: '+1', flag: '🇺🇸', name: 'USA' },
    { code: '+44', flag: '🇬🇧', name: 'UK' },
    { code: '+91', flag: '🇮🇳', name: 'India' },
    { code: '+92', flag: '🇵🇰', name: 'Pakistan' },
    { code: '+880', flag: '🇧🇩', name: 'Bangladesh' },
    { code: '+63', flag: '🇵🇭', name: 'Philippines' },
    { code: '+62', flag: '🇮🇩', name: 'Indonesia' },
    { code: '+60', flag: '🇲🇾', name: 'Malaysia' },
    { code: '+65', flag: '🇸🇬', name: 'Singapore' },
    { code: '+971', flag: '🇦🇪', name: 'UAE' },
    { code: '+966', flag: '🇸🇦', name: 'Saudi Arabia' },
    { code: '+20', flag: '🇪🇬', name: 'Egypt' },
    { code: '+234', flag: '🇳🇬', name: 'Nigeria' },
    { code: '+27', flag: '🇿🇦', name: 'South Africa' },
    { code: '+55', flag: '🇧🇷', name: 'Brazil' },
    { code: '+52', flag: '🇲🇽', name: 'Mexico' },
    { code: '+58', flag: '🇻🇪', name: 'Venezuela' },
    { code: '+54', flag: '🇦🇷', name: 'Argentina' },
    { code: '+56', flag: '🇨🇱', name: 'Chile' },
    { code: '+57', flag: '🇨🇴', name: 'Colombia' },
  ];

  useEffect(() => {
    loadStats();
    const interval = setInterval(loadStats, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    Animated.timing(successAnim, {
      toValue: successRate / 100,
      duration: 1000,
      useNativeDriver: false,
    }).start();
  }, [successRate]);

  const loadStats = async () => {
    try {
      const stats = await api.getStats();
      setTotalOps(stats.total_operations || 0);
      setSuccessRate(stats.success_rate || 0);
    } catch (error) {
      console.log('Stats load error:', error);
    }
  };

  const addLog = (message, type = 'info') => {
    const timestamp = new Date().toLocaleTimeString();
    const logEntry = { id: Date.now(), message, type, timestamp };
    setLogs(prev => [logEntry, ...prev].slice(0, 50));
    if (scrollViewRef.current) {
      setTimeout(() => scrollViewRef.current.scrollTo({ y: 0, animated: true }), 100);
    }
  };

  const executeQuickAction = async (action) => {
    if (!phoneNumber.trim()) {
      addLog('ERROR: Please enter a phone number', 'error');
      return;
    }
    setIsLoading(true);
    addLog(`EXECUTING: ${action.toUpperCase()} for ${countryCode}${phoneNumber}`, 'info');

    try {
      const result = await api.executeOperation({
        phone: `${countryCode}${phoneNumber}`,
        action: action,
      });
      if (result.success) {
        addLog(`SUCCESS: ${action.toUpperCase()} completed`, 'success');
      } else {
        addLog(`FAILED: ${result.error || 'Unknown error'}`, 'error');
      }
      addToHistory({
        phone: `${countryCode}${phoneNumber}`,
        action: action,
        success: result.success,
        message: result.message,
        error: result.error,
        duration: result.duration_seconds,
      });
    } catch (error) {
      addLog(`ERROR: ${error.message}`, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  const successInterpolate = successAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ['0%', '100%'],
  });

  const getLogColor = (type) => {
    switch (type) {
      case 'success': return theme.gold;
      case 'error': return theme.fire;
      case 'warning': return '#F59E0B';
      default: return theme.steel;
    }
  };

  const quickActions = [
    { label: 'BAN', icon: '🔴', action: 'permanent_ban', color: theme.fire },
    { label: 'UNBAN', icon: '🟢', action: 'permanent_unban', color: '#22C55E' },
    { label: 'STATUS', icon: '🔍', action: 'status_check', color: theme.steel },
  ];

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>🦅 EAGLE DASHBOARD</Text>
        <Text style={styles.headerSubtitle}>Live Operations Center</Text>
      </View>

      <View style={styles.statsGrid}>
        <View style={[styles.statCard, { borderColor: theme.gold }]}>
          <Text style={styles.statIcon}>⚡</Text>
          <Text style={styles.statValue}>{totalOps.toLocaleString()}</Text>
          <Text style={styles.statLabel}>TOTAL OPS</Text>
        </View>
        <View style={[styles.statCard, { borderColor: theme.fire }]}>
          <Text style={styles.statIcon}>🎯</Text>
          <Text style={styles.statValue}>{Math.round(successRate)}%</Text>
          <Text style={styles.statLabel}>SUCCESS RATE</Text>
          <View style={styles.progressBar}>
            <Animated.View
              style={[
                styles.progressFill,
                {
                  width: successInterpolate,
                  backgroundColor: theme.fire,
                },
              ]}
            />
          </View>
        </View>
      </View>

      <View style={styles.inputSection}>
        <Text style={styles.sectionTitle}>🎯 TARGET INPUT</Text>
        <View style={styles.inputRow}>
          <TouchableOpacity
            style={[styles.countrySelector, { borderColor: theme.darkGold }]}
            onPress={() => setShowCountryPicker(true)}>
            <Text style={styles.countryFlag}>{countryFlag}</Text>
            <Text style={[styles.countryCode, { color: theme.text }]}>{countryCode}</Text>
            <Text style={[styles.dropdownArrow, { color: theme.muted }]}>▼</Text>
          </TouchableOpacity>
          <TextInput
            style={[styles.phoneInput, { borderColor: theme.darkGold }]}
            value={phoneNumber}
            onChangeText={setPhoneNumber}
            placeholder="Phone Number"
            placeholderTextColor={theme.muted}
            keyboardType="phone-pad"
          />
        </View>

        {showCountryPicker && (
          <View style={[styles.countryPickerOverlay, { backgroundColor: 'rgba(0,0,0,0.8)' }]}>
            <View style={[styles.countryPicker, { backgroundColor: theme.card }]}>
              <View style={[styles.countryPickerHeader, { borderBottomColor: theme.darkGold }]}>
                <Text style={[styles.countryPickerTitle, { color: theme.gold }]}>SELECT COUNTRY</Text>
                <TouchableOpacity onPress={() => setShowCountryPicker(false)}>
                  <Text style={[styles.closeButton, { color: theme.fire }]}>✕</Text>
                </TouchableOpacity>
              </View>
              <ScrollView style={styles.countryList}>
                {COUNTRIES.map((country) => (
                  <TouchableOpacity
                    key={country.code}
                    style={[
                      styles.countryOption,
                      { borderBottomColor: theme.darkGold + '40' },
                      countryCode === country.code && { backgroundColor: theme.gold + '20' },
                    ]}
                    onPress={() => {
                      setCountryCode(country.code);
                      setCountryFlag(country.flag);
                      setShowCountryPicker(false);
                    }}>
                    <Text style={styles.countryFlagOption}>{country.flag}</Text>
                    <Text style={[styles.countryName, { color: theme.text }]}>{country.name}</Text>
                    <Text style={[styles.countryCodeOption, { color: theme.muted }]}>{country.code}</Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </View>
          </View>
        )}
      </View>

      <View style={styles.actionsSection}>
        <Text style={styles.sectionTitle}>⚡ QUICK ACTIONS</Text>
        <View style={styles.actionsGrid}>
          {quickActions.map((item) => (
            <TouchableOpacity
              key={item.action}
              style={[styles.actionButton, { backgroundColor: item.color + '20', borderColor: item.color }]}
              onPress={() => executeQuickAction(item.action)}
              disabled={isLoading}>
              <Text style={styles.actionIcon}>{item.icon}</Text>
              <Text style={[styles.actionLabel, { color: item.color }]}>{item.label}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      <View style={styles.terminalSection}>
        <View style={styles.terminalHeader}>
          <Text style={styles.terminalTitle}>🖥️ EAGLE EYE TERMINAL</Text>
          <View style={styles.terminalIndicator}>
            <View style={[styles.indicatorDot, { backgroundColor: isLoading ? theme.fire : theme.gold }]} />
            <Text style={styles.indicatorText}>{isLoading ? 'ACTIVE' : 'IDLE'}</Text>
          </View>
        </View>
        <ScrollView
          ref={scrollViewRef}
          style={styles.terminal}
          showsVerticalScrollIndicator={false}>
          {logs.length === 0 ? (
            <Text style={styles.terminalPlaceholder}>
              🦅 Eagle Eye is ready...{'\n'}Awaiting operations...
            </Text>
          ) : (
            logs.map((log) => (
              <View key={log.id} style={styles.logEntry}>
                <Text style={styles.logTime}>{log.timestamp}</Text>
                <Text style={[styles.logMessage, { color: getLogColor(log.type) }]}>
                  {log.message}
                </Text>
              </View>
            ))
          )}
        </ScrollView>
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
  },
  header: {
    alignItems: 'center',
    marginBottom: 24,
    paddingVertical: 16,
    borderBottomWidth: 2,
    borderBottomColor: theme.gold,
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: theme.gold,
    letterSpacing: 2,
  },
  headerSubtitle: {
    fontSize: 14,
    color: theme.muted,
    marginTop: 4,
  },
  statsGrid: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 20,
  },
  statCard: {
    flex: 1,
    backgroundColor: theme.card,
    borderRadius: 16,
    padding: 20,
    alignItems: 'center',
    borderWidth: 2,
    shadowColor: theme.gold,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  statIcon: {
    fontSize: 32,
    marginBottom: 8,
  },
  statValue: {
    fontSize: 28,
    fontWeight: 'bold',
    color: theme.gold,
  },
  statLabel: {
    fontSize: 12,
    color: theme.muted,
    marginTop: 4,
    fontWeight: '600',
    letterSpacing: 1,
  },
  progressBar: {
    width: '100%',
    height: 6,
    backgroundColor: theme.darker,
    borderRadius: 3,
    marginTop: 12,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: 3,
  },
  inputSection: {
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: theme.gold,
    marginBottom: 12,
    letterSpacing: 1,
  },
  inputRow: {
    flexDirection: 'row',
    gap: 12,
  },
  phoneInput: {
    flex: 1,
    height: 50,
    backgroundColor: theme.card,
    borderRadius: 12,
    paddingHorizontal: 16,
    color: theme.text,
    fontSize: 16,
    borderWidth: 1,
  },
  actionsSection: {
    marginBottom: 20,
  },
  actionsGrid: {
    flexDirection: 'row',
    gap: 12,
  },
  actionButton: {
    flex: 1,
    height: 80,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  actionIcon: {
    fontSize: 28,
    marginBottom: 4,
  },
  actionLabel: {
    fontSize: 12,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  terminalSection: {
    flex: 1,
    minHeight: 250,
    marginBottom: 20,
  },
  terminalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
    paddingHorizontal: 4,
  },
  terminalTitle: {
    fontSize: 14,
    fontWeight: 'bold',
    color: theme.gold,
    letterSpacing: 1,
  },
  terminalIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  indicatorDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  indicatorText: {
    fontSize: 12,
    color: theme.muted,
    fontWeight: '600',
  },
  terminal: {
    flex: 1,
    backgroundColor: '#000000',
    borderRadius: 12,
    padding: 12,
    minHeight: 200,
    borderWidth: 2,
    borderColor: theme.darkGold,
  },
  terminalPlaceholder: {
    color: theme.muted,
    fontSize: 14,
    lineHeight: 20,
    fontFamily: 'monospace',
  },
  logEntry: {
    flexDirection: 'row',
    marginBottom: 6,
    gap: 8,
  },
  logTime: {
    color: theme.darkGold,
    fontSize: 11,
    fontFamily: 'monospace',
    minWidth: 70,
  },
  logMessage: {
    flex: 1,
    fontSize: 13,
    fontFamily: 'monospace',
    lineHeight: 18,
  },
  countrySelector: {
    flexDirection: 'row',
    alignItems: 'center',
    width: 100,
    height: 50,
    backgroundColor: theme.card,
    borderRadius: 12,
    paddingHorizontal: 12,
    borderWidth: 1,
    gap: 6,
  },
  countryFlag: {
    fontSize: 20,
  },
  countryCode: {
    flex: 1,
    fontSize: 14,
    fontWeight: '600',
  },
  dropdownArrow: {
    fontSize: 10,
  },
  countryPickerOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 1000,
  },
  countryPicker: {
    width: '90%',
    maxHeight: '70%',
    borderRadius: 16,
    overflow: 'hidden',
    borderWidth: 2,
    borderColor: theme.darkGold,
  },
  countryPickerHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
  },
  countryPickerTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  closeButton: {
    fontSize: 24,
    fontWeight: 'bold',
  },
  countryList: {
    maxHeight: 300,
  },
  countryOption: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    padding: 14,
    borderBottomWidth: 1,
  },
  countryFlagOption: {
    fontSize: 24,
  },
  countryName: {
    flex: 1,
    fontSize: 14,
    fontWeight: '500',
  },
  countryCodeOption: {
    fontSize: 14,
    fontWeight: '600',
  },
});
