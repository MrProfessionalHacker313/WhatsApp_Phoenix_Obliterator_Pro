import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, TextInput, ScrollView, Animated, Dimensions,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useTheme } from '../context/ThemeContext';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

const HISTORY_KEY = '@eagle_operation_history';

export default function HistoryScreen({ navigation }) {
  const { theme } = useTheme();

  const FILTERS = [
    { key: 'all', label: 'ALL', color: theme.gold },
    { key: 'success', label: 'SUCCESS', color: '#22C55E' },
    { key: 'failed', label: 'FAILED', color: theme.fire },
  ];
  const [history, setHistory] = useState([]);
  const [filter, setFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedItem, setSelectedItem] = useState(null);
  const fadeAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    loadHistory();
  }, []);

  useEffect(() => {
    Animated.timing(fadeAnim, {
      toValue: 1,
      duration: 300,
      useNativeDriver: true,
    }).start();
  }, [history, filter]);

  const loadHistory = async () => {
    try {
      const stored = await AsyncStorage.getItem(HISTORY_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        setHistory(parsed.sort((a, b) => b.timestamp - a.timestamp));
      }
    } catch (error) {
      console.log('History load error:', error);
    }
  };

  const saveHistory = async (newHistory) => {
    try {
      await AsyncStorage.setItem(HISTORY_KEY, JSON.stringify(newHistory));
    } catch (error) {
      console.log('History save error:', error);
    }
  };

  const addToHistory = async (operation) => {
    const newEntry = {
      id: Date.now(),
      timestamp: Date.now(),
      phone: operation.phone,
      action: operation.action,
      success: operation.success || false,
      message: operation.message || operation.error || 'No details',
      duration: operation.duration || 0,
    };

    const newHistory = [newEntry, ...history].slice(0, 100);
    setHistory(newHistory);
    await saveHistory(newHistory);
  };

  const clearHistory = async () => {
    setHistory([]);
    await AsyncStorage.removeItem(HISTORY_KEY);
  };

  const getActionLabel = (action) => {
    const labels = {
      permanent_ban: 'PERM BAN',
      permanent_unban: 'PERM UNBAN',
      temporary_ban: 'TEMP BAN',
      temporary_unban: 'TEMP UNBAN',
      status_check: 'STATUS',
    };
    return labels[action] || action.toUpperCase();
  };

  const getActionColor = (action) => {
    const colors = {
      permanent_ban: theme.fire,
      permanent_unban: '#22C55E',
      temporary_ban: '#F59E0B',
      temporary_unban: '#3B82F6',
      status_check: theme.steel,
    };
    return colors[action] || theme.gold;
  };

  const filteredHistory = history.filter((item) => {
    const matchesFilter = filter === 'all' ||
      (filter === 'success' && item.success) ||
      (filter === 'failed' && !item.success);
    const matchesSearch = !searchQuery ||
      item.phone?.includes(searchQuery) ||
      item.action?.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  const formatDate = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (selectedItem) {
    return (
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => setSelectedItem(null)}>
            <Text style={styles.backButton}>← BACK</Text>
          </TouchableOpacity>
          <Text style={styles.headerTitle}>📋 OPERATION DETAIL</Text>
        </View>

        <View style={[styles.detailCard, { borderColor: getActionColor(selectedItem.action) }]}>
          <View style={[styles.detailHeader, { backgroundColor: getActionColor(selectedItem.action) + '20' }]}>
            <Text style={styles.detailIcon}>
              {selectedItem.success ? '✅' : '❌'}
            </Text>
            <Text style={[styles.detailTitle, { color: getActionColor(selectedItem.action) }]}>
              {getActionLabel(selectedItem.action)}
            </Text>
          </View>

          <View style={styles.detailBody}>
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Phone:</Text>
              <Text style={styles.detailValue}>{selectedItem.phone}</Text>
            </View>
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Status:</Text>
              <Text style={[styles.detailValue, { color: selectedItem.success ? '#22C55E' : theme.fire }]}>
                {selectedItem.success ? 'SUCCESS' : 'FAILED'}
              </Text>
            </View>
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Date:</Text>
              <Text style={styles.detailValue}>{formatDate(selectedItem.timestamp)}</Text>
            </View>
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Duration:</Text>
              <Text style={styles.detailValue}>{selectedItem.duration}s</Text>
            </View>
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Message:</Text>
              <Text style={styles.detailValue}>{selectedItem.message}</Text>
            </View>
          </View>
        </View>
      </ScrollView>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>📊 OPERATION HISTORY</Text>
        <Text style={styles.headerSubtitle}>{filteredHistory.length} records</Text>
      </View>

      <View style={styles.searchContainer}>
        <TextInput
          style={[styles.searchInput, { borderColor: theme.darkGold }]}
          value={searchQuery}
          onChangeText={setSearchQuery}
          placeholder="Search by phone number..."
          placeholderTextColor={theme.muted}
        />
      </View>

      <View style={styles.filterContainer}>
        {FILTERS.map((f) => (
          <TouchableOpacity
            key={f.key}
            style={[
              styles.filterButton,
              {
                backgroundColor: filter === f.key ? f.color + '30' : 'transparent',
                borderColor: f.color,
              },
            ]}
            onPress={() => setFilter(f.key)}>
            <Text style={[styles.filterText, { color: f.color }]}>{f.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {history.length > 0 && (
        <TouchableOpacity style={styles.clearButton} onPress={clearHistory}>
          <Text style={styles.clearButtonText}>🗑️ CLEAR HISTORY</Text>
        </TouchableOpacity>
      )}

      <Animated.View style={{ opacity: fadeAnim }}>
        {filteredHistory.length === 0 ? (
          <View style={styles.emptyState}>
            <Text style={styles.emptyIcon}>🦅</Text>
            <Text style={styles.emptyText}>No operations found</Text>
            <Text style={styles.emptySubtext}>
              {searchQuery ? 'Try a different search term' : 'Execute operations to build history'}
            </Text>
          </View>
        ) : (
          filteredHistory.map((item) => (
            <TouchableOpacity
              key={item.id}
              style={[styles.historyCard, { borderLeftColor: getActionColor(item.action) }]}
              onPress={() => setSelectedItem(item)}
              activeOpacity={0.7}>
              <View style={styles.historyHeader}>
                <Text style={[styles.historyAction, { color: getActionColor(item.action) }]}>
                  {getActionLabel(item.action)}
                </Text>
                <Text style={[
                  styles.historyStatus,
                  { color: item.success ? '#22C55E' : theme.fire }
                ]}>
                  {item.success ? '✓ SUCCESS' : '✗ FAILED'}
                </Text>
              </View>
              <Text style={styles.historyPhone}>{item.phone}</Text>
              <Text style={styles.historyDate}>{formatDate(item.timestamp)}</Text>
            </TouchableOpacity>
          ))
        )}
      </Animated.View>
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
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
    paddingBottom: 16,
    borderBottomWidth: 2,
    borderBottomColor: theme.gold,
  },
  backButton: {
    color: theme.gold,
    fontSize: 14,
    fontWeight: 'bold',
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
  },
  searchContainer: {
    marginBottom: 16,
  },
  searchInput: {
    height: 48,
    backgroundColor: theme.card,
    borderRadius: 12,
    paddingHorizontal: 16,
    color: theme.text,
    fontSize: 14,
    borderWidth: 1,
  },
  filterContainer: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 16,
  },
  filterButton: {
    flex: 1,
    height: 40,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1.5,
  },
  filterText: {
    fontSize: 12,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  clearButton: {
    alignSelf: 'flex-end',
    marginBottom: 16,
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
    backgroundColor: theme.fire + '20',
    borderWidth: 1,
    borderColor: theme.fire,
  },
  clearButtonText: {
    color: theme.fire,
    fontSize: 12,
    fontWeight: 'bold',
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyIcon: {
    fontSize: 60,
    marginBottom: 16,
  },
  emptyText: {
    fontSize: 18,
    color: theme.text,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  emptySubtext: {
    fontSize: 14,
    color: theme.muted,
  },
  historyCard: {
    backgroundColor: theme.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderLeftWidth: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 4,
  },
  historyHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  historyAction: {
    fontSize: 16,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  historyStatus: {
    fontSize: 12,
    fontWeight: 'bold',
  },
  historyPhone: {
    fontSize: 14,
    color: theme.text,
    marginBottom: 4,
  },
  historyDate: {
    fontSize: 12,
    color: theme.muted,
  },
  detailCard: {
    backgroundColor: theme.card,
    borderRadius: 16,
    borderWidth: 2,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  detailHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    padding: 20,
  },
  detailIcon: {
    fontSize: 32,
  },
  detailTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  detailBody: {
    padding: 20,
    gap: 16,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  detailLabel: {
    fontSize: 14,
    color: theme.muted,
    fontWeight: '600',
  },
  detailValue: {
    fontSize: 14,
    color: theme.text,
    fontWeight: '500',
    flex: 1,
    textAlign: 'right',
  },
});
