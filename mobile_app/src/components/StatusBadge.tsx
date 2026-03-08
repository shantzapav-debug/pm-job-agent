import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

type Status = 'applied' | 'manual' | 'pending' | 'failed';

const CONFIG: Record<Status, { label: string; bg: string; color: string }> = {
  applied:  { label: '✓ Applied',       bg: '#d1fae5', color: '#065f46' },
  manual:   { label: '✋ Apply Manually', bg: '#fef3c7', color: '#92400e' },
  pending:  { label: '⏳ Pending',       bg: '#e0e7ff', color: '#3730a3' },
  failed:   { label: '✗ Failed',         bg: '#fee2e2', color: '#991b1b' },
};

export default function StatusBadge({ status }: { status: string }) {
  const cfg = CONFIG[status as Status] ?? CONFIG.pending;
  return (
    <View style={[styles.badge, { backgroundColor: cfg.bg }]}>
      <Text style={[styles.label, { color: cfg.color }]}>{cfg.label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, alignSelf: 'flex-start' },
  label: { fontSize: 12, fontWeight: '600' },
});
