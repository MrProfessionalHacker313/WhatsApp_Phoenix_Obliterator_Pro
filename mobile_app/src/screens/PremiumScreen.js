import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, Animated, Dimensions, Alert, Platform,
} from 'react-native';
import { useStripe } from '@stripe/stripe-react-native';
import * as RNIap from 'react-native-iap';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useTheme } from '../context/ThemeContext';
import api from '../services/api';

const PLANS = [
  {
    id: 'basic',
    name: 'BASIC',
    price: '$4.99',
    period: '/month',
    emoji: '🥉',
    color: '#F59E0B',
    operations: '50 operations/month',
    features: ['50 operations/month', 'Email support', 'Standard speed', 'Basic analytics'],
    productId: Platform.select({ ios: 'com.phoenix.basic', android: 'com.phoenix.basic' }),
  },
  {
    id: 'pro',
    name: 'PRO',
    price: '$14.99',
    period: '/month',
    emoji: '🥈',
    color: '#FFD700',
    operations: 'Unlimited operations',
    features: ['Unlimited operations', 'Priority support', 'Fast processing', 'Advanced analytics', 'API access'],
    productId: Platform.select({ ios: 'com.phoenix.pro', android: 'com.phoenix.pro' }),
    popular: true,
  },
  {
    id: 'elite',
    name: 'ELITE',
    price: '$49.99',
    period: 'lifetime',
    emoji: '🥇',
    color: '#EF4444',
    operations: 'Everything forever',
    features: ['Lifetime access', 'VIP support', 'Instant processing', 'Full analytics', 'API access', 'Custom strategies', 'White-label rights'],
    productId: Platform.select({ ios: 'com.phoenix.elite', android: 'com.phoenix.elite' }),
  },
];

const CURRENT_PLAN_KEY = '@eagle_current_plan';

export default function PremiumScreen({ navigation }) {
  const { theme } = useTheme();
  const [currentPlan, setCurrentPlan] = useState(null);
  const [isTrialActive, setIsTrialActive] = useState(false);
  const [trialDaysLeft, setTrialDaysLeft] = useState(3);
  const [isProcessing, setIsProcessing] = useState(false);
  const [products, setProducts] = useState([]);
  const scaleAnims = useRef({}).current;
  const { initPaymentSheet, presentPaymentSheet } = useStripe();

  useEffect(() => {
    loadCurrentPlan();
    checkTrialStatus();
    setupIAP();
  }, []);

  useEffect(() => {
    PLANS.forEach((plan) => {
      if (!scaleAnims[plan.id]) {
        scaleAnims[plan.id] = new Animated.Value(1);
      }
    });
  }, []);

  const loadCurrentPlan = async () => {
    try {
      const stored = await AsyncStorage.getItem(CURRENT_PLAN_KEY);
      if (stored) {
        const plan = JSON.parse(stored);
        setCurrentPlan(plan);
      }
    } catch (error) {
      console.log('Plan load error:', error);
    }
  };

  const checkTrialStatus = async () => {
    try {
      const trialEnd = await AsyncStorage.getItem('@eagle_trial_end');
      if (trialEnd) {
        const endDate = new Date(trialEnd);
        const now = new Date();
        const daysLeft = Math.ceil((endDate - now) / (1000 * 60 * 60 * 24));
        if (daysLeft > 0) {
          setIsTrialActive(true);
          setTrialDaysLeft(daysLeft);
        }
      }
    } catch (error) {
      console.log('Trial check error:', error);
    }
  };

  const setupIAP = async () => {
    try {
      const products = await RNIap.getProducts(PLANS.map(p => p.productId).filter(Boolean));
      setProducts(products);
    } catch (error) {
      console.log('IAP setup error:', error);
    }
  };

  const startTrial = async () => {
    try {
      const trialEnd = new Date();
      trialEnd.setDate(trialEnd.getDate() + 3);
      await AsyncStorage.setItem('@eagle_trial_end', trialEnd.toISOString());
      await AsyncStorage.setItem(CURRENT_PLAN_KEY, JSON.stringify({
        id: 'trial',
        name: 'TRIAL',
        expiresAt: trialEnd.toISOString(),
      }));
      setIsTrialActive(true);
      setTrialDaysLeft(3);
      Alert.alert('Trial Started', 'Your 3-day free trial has begun!');
    } catch (error) {
      Alert.alert('Error', 'Failed to start trial');
    }
  };

  const purchaseWithStripe = async (plan) => {
    setIsProcessing(true);
    try {
      const response = await api.createStripeCheckoutSession({
        plan: plan.id,
        email: 'user@example.com',
      });

      if (response.ok && response.session_url) {
        Alert.alert(
          'Payment',
          'Redirecting to Stripe checkout...',
          [
            {
              text: 'OK',
              onPress: () => {
                // In a real app, you would open the URL in a WebView or browser
                Alert.alert('Stripe', `Checkout URL: ${response.session_url}`);
              },
            },
          ]
        );
      } else {
        Alert.alert('Error', response.error || 'Failed to create checkout session');
      }
    } catch (error) {
      Alert.alert('Error', error.message);
    } finally {
      setIsProcessing(false);
    }
  };

  const purchaseWithIAP = async (plan) => {
    try {
      const product = products.find(p => p.productId === plan.productId);
      if (!product) {
        Alert.alert('Error', 'Product not available');
        return;
      }

      const purchase = await RNIap.requestPurchase(product.productId);
      if (purchase.productId === plan.productId) {
        await AsyncStorage.setItem(CURRENT_PLAN_KEY, JSON.stringify({
          id: plan.id,
          name: plan.name,
          price: plan.price,
          productId: plan.productId,
        }));
        setCurrentPlan({
          id: plan.id,
          name: plan.name,
          price: plan.price,
          productId: plan.productId,
        });
        Alert.alert('Success', `${plan.name} plan activated!`);
      }
    } catch (error) {
      if (error.code !== 'E_USER_CANCELLED') {
        Alert.alert('Purchase Error', error.message);
      }
    }
  };

  const handlePurchase = async (plan) => {
    if (isProcessing) return;

    Animated.sequence([
      Animated.timing(scaleAnims[plan.id], {
        toValue: 0.95,
        duration: 100,
        useNativeDriver: true,
      }),
      Animated.timing(scaleAnims[plan.id], {
        toValue: 1,
        duration: 100,
        useNativeDriver: true,
      }),
    ]).start();

    if (Platform.OS === 'ios' || Platform.OS === 'android') {
      await purchaseWithIAP(plan);
    } else {
      await purchaseWithStripe(plan);
    }
  };

  const getCurrentPlanDisplay = () => {
    if (!currentPlan) return 'No active plan';
    if (currentPlan.id === 'trial') return `TRIAL (${trialDaysLeft} days left)`;
    return `${currentPlan.name} - ${currentPlan.price}`;
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>💰 PREMIUM PLANS</Text>
        <Text style={styles.headerSubtitle}>Unlock Full Eagle Power</Text>
      </View>

      <View style={[styles.statusCard, { borderColor: theme.gold }]}>
        <Text style={styles.statusTitle}>CURRENT PLAN</Text>
        <Text style={[styles.statusValue, { color: currentPlan ? theme.gold : theme.muted }]}>
          {getCurrentPlanDisplay()}
        </Text>
        {isTrialActive && (
          <View style={styles.trialBadge}>
            <Text style={styles.trialText}>TRIAL ACTIVE - {trialDaysLeft} DAYS LEFT</Text>
          </View>
        )}
      </View>

      {!currentPlan && !isTrialActive && (
        <TouchableOpacity style={styles.trialButton} onPress={startTrial}>
          <Text style={styles.trialButtonText}>🎁 TRY FREE FOR 3 DAYS</Text>
          <Text style={styles.trialButtonSubtext}>No credit card required</Text>
        </TouchableOpacity>
      )}

      <View style={styles.plansContainer}>
        {PLANS.map((plan) => (
          <Animated.View
            key={plan.id}
            style={[
              styles.planCard,
              {
                borderColor: plan.color,
                transform: [{ scale: scaleAnims[plan.id] || 1 }],
              },
              plan.popular && styles.popularCard,
            ]}>
            {plan.popular && (
              <View style={[styles.popularBadge, { backgroundColor: plan.color }]}>
                <Text style={styles.popularText}>MOST POPULAR</Text>
              </View>
            )}

            <View style={styles.planHeader}>
              <Text style={styles.planEmoji}>{plan.emoji}</Text>
              <Text style={[styles.planName, { color: plan.color }]}>{plan.name}</Text>
              <View style={styles.priceContainer}>
                <Text style={styles.planPrice}>{plan.price}</Text>
                <Text style={styles.planPeriod}>{plan.period}</Text>
              </View>
              <Text style={[styles.planOperations, { color: theme.muted }]}>
                {plan.operations}
              </Text>
            </View>

            <View style={styles.featuresContainer}>
              {plan.features.map((feature, index) => (
                <View key={index} style={styles.featureRow}>
                  <Text style={[styles.featureCheck, { color: plan.color }]}>✓</Text>
                  <Text style={styles.featureText}>{feature}</Text>
                </View>
              ))}
            </View>

            <TouchableOpacity
              style={[styles.purchaseButton, { backgroundColor: plan.color }]}
              onPress={() => handlePurchase(plan)}
              disabled={isProcessing}>
              <Text style={styles.purchaseButtonText}>
                {isProcessing ? 'PROCESSING...' : currentPlan?.id === plan.id ? 'ACTIVE' : 'SUBSCRIBE'}
              </Text>
            </TouchableOpacity>
          </Animated.View>
        ))}
      </View>

      <View style={styles.footer}>
        <Text style={styles.footerText}>
          Secure payments powered by Stripe{'\n'}
          Auto-renews unless cancelled. 7-day refund policy.
        </Text>
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
  statusCard: {
    backgroundColor: theme.card,
    borderRadius: 16,
    padding: 20,
    alignItems: 'center',
    marginBottom: 20,
    borderWidth: 2,
    shadowColor: theme.gold,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  statusTitle: {
    fontSize: 12,
    color: theme.muted,
    fontWeight: '600',
    letterSpacing: 2,
    marginBottom: 8,
  },
  statusValue: {
    fontSize: 18,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  trialBadge: {
    marginTop: 12,
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: theme.gold + '20',
    borderWidth: 1,
    borderColor: theme.gold,
  },
  trialText: {
    color: theme.gold,
    fontSize: 12,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  trialButton: {
    backgroundColor: theme.gold + '20',
    borderRadius: 16,
    padding: 20,
    alignItems: 'center',
    marginBottom: 20,
    borderWidth: 2,
    borderColor: theme.gold,
    shadowColor: theme.gold,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  trialButtonText: {
    fontSize: 18,
    fontWeight: 'bold',
    color: theme.gold,
    letterSpacing: 2,
  },
  trialButtonSubtext: {
    fontSize: 12,
    color: theme.muted,
    marginTop: 4,
  },
  plansContainer: {
    gap: 16,
  },
  planCard: {
    backgroundColor: theme.card,
    borderRadius: 20,
    borderWidth: 2,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  popularCard: {
    borderWidth: 3,
    shadowColor: theme.gold,
    shadowOpacity: 0.5,
  },
  popularBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderBottomRightRadius: 12,
  },
  popularText: {
    color: theme.text,
    fontSize: 11,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  planHeader: {
    alignItems: 'center',
    padding: 24,
    borderBottomWidth: 1,
    borderBottomColor: theme.darkGold + '40',
  },
  planEmoji: {
    fontSize: 40,
    marginBottom: 12,
  },
  planName: {
    fontSize: 20,
    fontWeight: 'bold',
    letterSpacing: 2,
    marginBottom: 8,
  },
  priceContainer: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 4,
    marginBottom: 8,
  },
  planPrice: {
    fontSize: 32,
    fontWeight: 'bold',
    color: theme.text,
  },
  planPeriod: {
    fontSize: 14,
    color: theme.muted,
  },
  planOperations: {
    fontSize: 14,
    fontWeight: '600',
  },
  featuresContainer: {
    padding: 20,
    gap: 12,
  },
  featureRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  featureCheck: {
    fontSize: 16,
    fontWeight: 'bold',
  },
  featureText: {
    flex: 1,
    fontSize: 14,
    color: theme.text,
  },
  purchaseButton: {
    marginHorizontal: 20,
    marginBottom: 20,
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
  purchaseButtonText: {
    color: theme.text,
    fontSize: 16,
    fontWeight: 'bold',
    letterSpacing: 2,
  },
  footer: {
    alignItems: 'center',
    paddingVertical: 20,
  },
  footerText: {
    fontSize: 12,
    color: theme.muted,
    textAlign: 'center',
    lineHeight: 18,
  },
});
