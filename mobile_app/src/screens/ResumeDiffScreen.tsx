import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator, Alert, ScrollView, Share,
  StyleSheet, Text, TouchableOpacity, View,
} from 'react-native';
import { ResumeData, jobsApi } from '../services/api';

export default function ResumeDiffScreen({ route }: any) {
  const { jobId } = route.params;
  const [data, setData] = useState<ResumeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<'changes' | 'tailored' | 'original'>('changes');

  useEffect(() => {
    jobsApi.resume(jobId)
      .then((r) => setData(r.data))
      .catch(() => Alert.alert('Error', 'Failed to load resume data'))
      .finally(() => setLoading(false));
  }, [jobId]);

  if (loading) return <View style={styles.center}><ActivityIndicator size="large" color="#2563eb" /></View>;
  if (!data) return <View style={styles.center}><Text>No data</Text></View>;

  const changes = data.changes_log || [];
  const addedChanges = changes.filter((c) => c.type === 'added');
  const modifiedChanges = changes.filter((c) => c.type === 'modified');
  const removedChanges = changes.filter((c) => c.type === 'removed');

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ paddingBottom: 40 }}>
      {/* Summary header */}
      <View style={styles.summary}>
        <Text style={styles.summaryTitle}>{data.title}</Text>
        <Text style={styles.summaryCompany}>{data.company}</Text>
        <View style={styles.statRow}>
          <View style={styles.statBox}>
            <Text style={styles.statNum}>{data.change_percentage}%</Text>
            <Text style={styles.statLabel}>Total Changed</Text>
          </View>
          <View style={styles.statBox}>
            <Text style={styles.statNum}>{changes.length}</Text>
            <Text style={styles.statLabel}>Edits</Text>
          </View>
          <View style={styles.statBox}>
            <Text style={styles.statNum}>{data.keywords_added?.length ?? 0}</Text>
            <Text style={styles.statLabel}>Keywords</Text>
          </View>
        </View>

        {data.keywords_added?.length > 0 && (
          <View style={styles.kwRow}>
            {data.keywords_added.map((k, i) => (
              <Text key={i} style={styles.kwChip}>{k}</Text>
            ))}
          </View>
        )}
      </View>

      {/* View toggle */}
      <View style={styles.tabs}>
        {(['changes', 'tailored', 'original'] as const).map((v) => (
          <TouchableOpacity key={v} style={[styles.tab, view === v && styles.activeTab]} onPress={() => setView(v)}>
            <Text style={[styles.tabText, view === v && styles.activeTabText]}>
              {v === 'changes' ? 'Changes' : v === 'tailored' ? 'Tailored' : 'Original'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Changes view */}
      {view === 'changes' && (
        <View style={styles.content}>
          {changes.length === 0 && (
            <Text style={styles.emptyText}>No changes logged.</Text>
          )}

          {modifiedChanges.length > 0 && (
            <View style={styles.group}>
              <Text style={styles.groupTitle}>✏️ Modified ({modifiedChanges.length})</Text>
              {modifiedChanges.map((c, i) => (
                <View key={i} style={styles.changeCard}>
                  {c.section ? <Text style={styles.changeSection}>{c.section}</Text> : null}
                  <View style={styles.changeRow}>
                    <View style={[styles.changeSide, { borderColor: '#fca5a5' }]}>
                      <Text style={styles.changeLabel}>Before</Text>
                      <Text style={styles.changeText}>{c.original || '—'}</Text>
                    </View>
                    <Text style={styles.arrow}>→</Text>
                    <View style={[styles.changeSide, { borderColor: '#86efac' }]}>
                      <Text style={styles.changeLabel}>After</Text>
                      <Text style={styles.changeText}>{c.updated || '—'}</Text>
                    </View>
                  </View>
                  {c.reason ? <Text style={styles.reason}>💡 {c.reason}</Text> : null}
                </View>
              ))}
            </View>
          )}

          {addedChanges.length > 0 && (
            <View style={styles.group}>
              <Text style={styles.groupTitle}>➕ Added ({addedChanges.length})</Text>
              {addedChanges.map((c, i) => (
                <View key={i} style={[styles.changeCard, { borderLeftColor: '#22c55e' }]}>
                  {c.section ? <Text style={styles.changeSection}>{c.section}</Text> : null}
                  <Text style={[styles.changeText, { color: '#166534' }]}>{c.updated}</Text>
                  {c.reason ? <Text style={styles.reason}>💡 {c.reason}</Text> : null}
                </View>
              ))}
            </View>
          )}

          {removedChanges.length > 0 && (
            <View style={styles.group}>
              <Text style={styles.groupTitle}>➖ Removed ({removedChanges.length})</Text>
              {removedChanges.map((c, i) => (
                <View key={i} style={[styles.changeCard, { borderLeftColor: '#ef4444' }]}>
                  {c.section ? <Text style={styles.changeSection}>{c.section}</Text> : null}
                  <Text style={[styles.changeText, { color: '#991b1b', textDecorationLine: 'line-through' }]}>{c.original}</Text>
                  {c.reason ? <Text style={styles.reason}>💡 {c.reason}</Text> : null}
                </View>
              ))}
            </View>
          )}
        </View>
      )}

      {/* Tailored / Original resume text view */}
      {(view === 'tailored' || view === 'original') && (
        <View style={styles.content}>
          {view === 'tailored' && !!data.tailored_resume_text && (
            <TouchableOpacity
              style={styles.shareBtn}
              onPress={() => Share.share({
                title: `Resume for ${data.title} @ ${data.company}`,
                message: data.tailored_resume_text,
              })}
            >
              <Text style={styles.shareBtnText}>Share / Copy Tailored Resume</Text>
            </TouchableOpacity>
          )}
          <View style={styles.resumeBox}>
            <Text style={styles.resumeText}>
              {view === 'tailored' ? (data.tailored_resume_text || 'No tailored version') : (data.original_resume_text || 'No original text')}
            </Text>
          </View>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f8fafc' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  summary: { backgroundColor: '#fff', padding: 20, borderBottomWidth: 1, borderBottomColor: '#e2e8f0' },
  summaryTitle: { fontSize: 16, fontWeight: '700', color: '#0f172a' },
  summaryCompany: { fontSize: 13, color: '#475569', marginBottom: 14 },
  statRow: { flexDirection: 'row', gap: 10, marginBottom: 12 },
  statBox: { flex: 1, backgroundColor: '#eff6ff', borderRadius: 10, padding: 10, alignItems: 'center' },
  statNum: { fontSize: 22, fontWeight: '800', color: '#2563eb' },
  statLabel: { fontSize: 10, color: '#64748b', marginTop: 2 },
  kwRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  kwChip: { backgroundColor: '#dbeafe', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, fontSize: 12, color: '#1d4ed8', fontWeight: '500' },
  tabs: { flexDirection: 'row', padding: 12, gap: 8 },
  tab: { flex: 1, paddingVertical: 8, borderRadius: 8, backgroundColor: '#e2e8f0', alignItems: 'center' },
  activeTab: { backgroundColor: '#2563eb' },
  tabText: { fontSize: 13, fontWeight: '600', color: '#475569' },
  activeTabText: { color: '#fff' },
  content: { paddingHorizontal: 12 },
  emptyText: { textAlign: 'center', color: '#94a3b8', marginTop: 40 },
  group: { marginBottom: 16 },
  groupTitle: { fontSize: 14, fontWeight: '700', color: '#0f172a', marginBottom: 8 },
  changeCard: { backgroundColor: '#fff', borderRadius: 10, padding: 12, marginBottom: 8, borderLeftWidth: 4, borderLeftColor: '#f59e0b', shadowColor: '#000', shadowOpacity: 0.04, shadowRadius: 3, elevation: 1 },
  changeSection: { fontSize: 11, fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', marginBottom: 6 },
  changeRow: { flexDirection: 'row', gap: 6, alignItems: 'flex-start' },
  changeSide: { flex: 1, borderWidth: 1, borderRadius: 6, padding: 8 },
  changeLabel: { fontSize: 10, fontWeight: '700', color: '#94a3b8', marginBottom: 4, textTransform: 'uppercase' },
  changeText: { fontSize: 12, color: '#334155', lineHeight: 17 },
  arrow: { fontSize: 16, color: '#94a3b8', marginTop: 18 },
  reason: { fontSize: 12, color: '#0369a1', marginTop: 8, fontStyle: 'italic' },
  shareBtn: { backgroundColor: '#2563eb', borderRadius: 10, padding: 12, alignItems: 'center', marginBottom: 10 },
  shareBtnText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  resumeBox: { backgroundColor: '#fff', borderRadius: 10, padding: 16 },
  resumeText: { fontSize: 12, color: '#334155', lineHeight: 19, fontFamily: 'monospace' },
});
