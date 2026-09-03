import React, { useState, useRef } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, TextInput, Animated, Dimensions, ScrollView,
} from 'react-native';
import * as Haptics from 'expo-haptics';
import { useTheme } from '../context/ThemeContext';
import api from '../services/api';
import { addToHistory } from '../services/history';

const OPERATIONS = [
  {
    id: 'permanent_ban',
    title: 'PERMANENT BAN',
    icon: '🔴',
    color: theme.fire,
    description: 'Total annihilation - 100% permanent removal',
  },
  {
    id: 'permanent_unban',
    title: 'PERMANENT UNBAN',
    icon: '🟢',
    color: '#22C55E',
    description: 'Full account recovery and restoration',
  },
  {
    id: 'temporary_ban',
    title: 'TEMPORARY BAN',
    icon: '🟡',
    color: '#F59E0B',
    description: 'Time-locked strike with custom duration',
    hasDuration: true,
  },
  {
    id: 'temporary_unban',
    title: 'TEMPORARY UNBAN',
    icon: '🔵',
    color: '#3B82F6',
    description: 'Early unlock ahead of schedule',
  },
];

export default function OperationsScreen({ navigation }) {
  const { theme } = useTheme();
  const [expandedCard, setExpandedCard] = useState(null);
  const [phoneNumber, setPhoneNumber] = useState('');
  const [duration, setDuration] = useState('24');
  const [isProcessing, setIsProcessing] = useState(false);
  const [results, setResults] = useState({});
  const cardAnims = useRef({}).current;

  OPERATIONS.forEach((op) => {
    if (!cardAnims[op.id]) {
      cardAnims[op.id] = {
        expandAnim: new Animated.Value(0),
        scaleAnim: new Animated.Value(1),
        progressAnim: new Animated.Value(0),
        resultOpacity: new Animated.Value(0),
      };
    }
  });

  const toggleCard = (id) => {
    if (expandedCard === id) {
      Animated.timing(cardAnims[id].expandAnim, {
        toValue: 0,
        duration: 200,
        useNativeDriver: false,
      }).start(() => setExpandedCard(null));
    } else {
      if (expandedCard && cardAnims[expandedCard]) {
        Animated.timing(cardAnims[expandedCard].expandAnim, {
          toValue: 0,
          duration: 150,
          useNativeDriver: false,
        }).start();
      }
      setExpandedCard(id);
      Animated.timing(cardAnims[id].expandAnim, {
        toValue: 1,
        duration: 250,
        useNativeDriver: false,
      }).start();
    }
  };

  const executeOperation = async (operationId) => {
    if (!phoneNumber.trim()) {
      alert('Please enter a phone number');
      return;
    }

    setIsProcessing(true);
    const anims = cardAnims[operationId];

    Animated.sequence([
      Animated.timing(anims.scaleAnim, {
        toValue: 0.95,
        duration: 100,
        useNativeDriver: true,
      }),
      Animated.timing(anims.scaleAnim, {
        toValue: 1,
        duration: 100,
        useNativeDriver: true,
      }),
      Animated.timing(anims.progressAnim, {
        toValue: 1,
        duration: 2000,
        useNativeDriver: false,
      }),
    ]).start();

    try {
      const payload = {
        phone: phoneNumber,
        action: operationId,
      };
      if (operationId === 'temporary_ban') {
        payload.duration = parseInt(duration) || 24;
      }

      const result = await api.executeOperation(payload);

      Animated.timing(anims.resultOpacity, {
        toValue: 1,
        duration: 300,
        useNativeDriver: true,
      }).start();

      setResults((prev) => ({
        ...prev,
        [operationId]: { success: result.success, message: result.message || result.error },
      }));

      addToHistory({
        phone: phoneNumber,
        action: operationId,
        success: result.success,
        message: result.message || result.error,
        duration: result.duration_seconds,
      });
    } catch (error) {
      Animated.timing(anims.resultOpacity, {
        toValue: 1,
        duration: 300,
        useNativeDriver: true,
      }).start();

      setResults((prev) => ({
        ...prev,
        [operationId]: { success: false, message: error.message },
      }));

      addToHistory({
        phone: phoneNumber,
        action: operationId,
        success: false,
        message: error.message,
      });
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>⚡ OPERATIONS CENTER</Text>
        <Text style={styles.headerSubtitle}>Eagle Strike Protocol</Text>
      </View>

      {OPERATIONS.map((op) => {
        const anims = cardAnims[op.id];
        const isExpanded = expandedCard === op.id;
        const result = results[op.id];

        const cardHeight = anims?.expandAnim.interpolate({
          inputRange: [0, 1],
          outputRange: [140, 320],
        }) || 140;

        const expandOpacity = anims?.expandAnim || 0;

        const progressInterpolate = anims?.progressAnim?.interpolate({
          inputRange: [0, 1],
          outputRange: ['0%', '100%'],
        }) || '0%';

        return (
          <Animated.View
            key={op.id}
            style={[
              styles.cardContainer,
              {
                height: isExpanded ? cardHeight : 140,
                borderColor: op.color,
                transform: [{ scale: anims?.scaleAnim || 1 }],
              },
            ]}>
            <TouchableOpacity
              style={[styles.cardHeader, { backgroundColor: op.color + '15' }]}
              onPress={() => toggleCard(op.id)}
              activeOpacity={0.8}>
              <View style={styles.cardHeaderLeft}>
                <Text style={styles.cardIcon}>{op.icon}</Text>
                <View>
                  <Text style={[styles.cardTitle, { color: op.color }]}>{op.title}</Text>
                  <Text style={styles.cardDescription}>{op.description}</Text>
                </View>
              </View>
              <Text style={[styles.expandIcon, { color: op.color }]}>
                {isExpanded ? '▾' : '▸'}
              </Text>
            </TouchableOpacity>

            <Animated.View style={[styles.cardBody, { opacity: expandOpacity }]}>
              <View style={styles.inputRow}>
                <TextInput
                  style={[styles.input, { borderColor: op.color + '60' }]}
                  value={isExpanded ? phoneNumber : ''}
                  onChangeText={isExpanded ? setPhoneNumber : undefined}
                  placeholder="Phone Number (e.g. 923001234567)"
                  placeholderTextColor={theme.muted}
                  keyboardType="phone-pad"
                  editable={isExpanded}
                />
                {op.hasDuration && isExpanded && (
                  <TextInput
                    style={[styles.durationInput, { borderColor: op.color + '60' }]}
                    value={duration}
                    onChangeText={setDuration}
                    placeholder="Hours"
                    placeholderTextColor={theme.muted}
                    keyboardType="numeric"
                  />
                )}
              </View>

              {isExpanded && (
                <View style={styles.confirmSection}>
                  <TouchableOpacity
                    style={[styles.confirmButton, { backgroundColor: op.color }]}
                    onPress={async () => {
                      await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
                      executeOperation(op.id);
                    }}
                    disabled={isProcessing}>
                    <Text style={styles.confirmButtonText}>
                      {isProcessing ? '🔄 PROCESSING...' : '✓ CONFIRM'}
                    </Text>
                  </TouchableOpacity>

                  {isProcessing && (
                    <View style={styles.progressContainer}>
                      <View style={[styles.progressBar, { backgroundColor: op.color + '30' }]}>
                        <Animated.View
                          style={[
                            styles.progressFill,
                            {
                              width: progressInterpolate,
                              backgroundColor: op.color,
                            },
                          ]}
                        />
                      </View>
                      <Text style={[styles.progressText, { color: op.color }]}>
                        Executing operation...
                      </Text>
                    </View>
                  )}

                  {result && (
                    <Animated.View
                      style={[
                        styles.resultContainer,
                        {
                          opacity: anims?.resultOpacity || 1,
                          backgroundColor: result.success ? '#22C55E20' : theme.fire + '20',
                          borderColor: result.success ? '#22C55E' : theme.fire,
                        },
                      ]}>
                      <Text style={[styles.resultIcon, { color: result.success ? '#22C55E' : theme.fire }]}>
                        {result.success ? '✅' : '❌'}
                      </Text>
                      <Text style={[styles.resultText, { color: result.success ? '#22C55E' : theme.fire }]}>
                        {result.success ? 'OPERATION SUCCESSFUL' : 'OPERATION FAILED'}
                      </Text>
                      <Text style={styles.resultMessage}>{result.message}</Text>
                    </Animated.View>
                  )}
                </View>
              )}
            </Animated.View>
          </Animated.View>
        );
      })}
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
  cardContainer: {
    backgroundColor: theme.card,
    borderRadius: 16,
    marginBottom: 16,
    borderWidth: 2,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    minHeight: 100,
  },
  cardHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    gap: 12,
  },
  cardIcon: {
    fontSize: 36,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  cardDescription: {
    fontSize: 12,
    color: theme.muted,
    marginTop: 2,
  },
  expandIcon: {
    fontSize: 24,
    fontWeight: 'bold',
  },
  cardBody: {
    padding: 16,
    borderTopWidth: 1,
    borderTopColor: theme.darkGold + '40',
  },
  inputRow: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 16,
  },
  input: {
    flex: 1,
    height: 48,
    backgroundColor: theme.darker,
    borderRadius: 12,
    paddingHorizontal: 16,
    color: theme.text,
    fontSize: 14,
    borderWidth: 1,
  },
  durationInput: {
    width: 80,
    height: 48,
    backgroundColor: theme.darker,
    borderRadius: 12,
    paddingHorizontal: 16,
    color: theme.text,
    fontSize: 14,
    borderWidth: 1,
    textAlign: 'center',
  },
  confirmSection: {
    gap: 12,
  },
  confirmButton: {
    height: 50,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  confirmButtonText: {
    color: theme.text,
    fontSize: 16,
    fontWeight: 'bold',
    letterSpacing: 2,
  },
  progressContainer: {
    gap: 8,
  },
  progressBar: {
    height: 8,
    borderRadius: 4,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: 4,
  },
  progressText: {
    fontSize: 12,
    textAlign: 'center',
    fontWeight: '600',
  },
  resultContainer: {
    padding: 16,
    borderRadius: 12,
    borderWidth: 2,
    alignItems: 'center',
    gap: 8,
  },
  resultIcon: {
    fontSize: 32,
  },
  resultText: {
    fontSize: 16,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  resultMessage: {
    fontSize: 12,
    color: theme.muted,
    textAlign: 'center',
  },
});
