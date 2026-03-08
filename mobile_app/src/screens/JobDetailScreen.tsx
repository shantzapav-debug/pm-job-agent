import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator, Alert, Linking, ScrollView,
  StyleSheet, Text, TouchableOpacity, View,
} from 'react-native';
import StatusBadge from '../components/StatusBadge';
import { JobDetail, jobsApi } from '../services/api';

export default function JobDetailScreen({ route, navigation }: any) {
  const { jobId } = route.params;
  const [job, setJob] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [marking, setMarking] = useState(false);

  useEffect(() => {
    jobsApi.detail(jobId).then((r) => {
      setJob(r.data);
      navigation.setOptions({ title: r.data.company });
    }).catch(() => Alert.alert('Error', 'Failed to load job')).finally(() => setLoading(false));
  }, [jobId]);

  const markApplied = async () => {
    setMarking(true);
    try {
      await jobsApi.markApplied(jobId);
      setJob((j) => j ? { ...j, status: 'applied' } : j);
      Alert.alert('Done', 'Marked as applied!');
    } catch (_) {
      Alert.alert('Error', 'Failed to update status');
    } finally {
      setMarking(false);
    }
  };

  const openLink = () => { if (job?.job_url) Linking.openURL(job.job_url); };

  if (loading) return <View style={styles.center}><ActivityIndicator size="large" color="#2563eb" /></View>;
  if (!job) return <View style={styles.center}><Text>Job not found</Text></View>;

  const changes = job.changes_log || [];

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ paddingBottom: 40 }}>
      {/* Hero */}
      <View style={styles.hero}>
        <StatusBadge status={job.status} />
        <Text style={styles.title}>{job.title}</Text>
        <Text style={styles.company}>{job.company}</Text>
        <Text style={styles.meta}>{job.location} · {job.source.toUpperCase()}</Text>

        <View style={styles.chips}>
          {job.experience_required ? <Text style={styles.chip}>{job.experience_required}</Text> : null}
          {job.salary_range && job.salary_range !== 'Not disclosed' ? <Text style={styles.chip}>{job.salary_range}</Text> : null}
          {job.posted_date ? <Text style={styles.chip}>{job.posted_date}</Text> : null}
        </View>
      </View>

      {/* Tailoring Stats */}
      {job.change_percentage > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Resume Tailoring</Text>
          <View style={styles.statRow}>
            <View style={styles.statBox}>
              <Text style={styles.statNum}>{job.change_percentage}%</Text>
              <Text style={styles.statLabel}>Changed</Text>
            </View>
            <View style={styles.statBox}>
              <Text style={styles.statNum}>{changes.length}</Text>
              <Text style={styles.statLabel}>Edits Made</Text>
            </View>
            <View style={styles.statBox}>
              <Text style={styles.statNum}>{job.keywords_added?.length ?? 0}</Text>
              <Text style={styles.statLabel}>Keywords Added</Text>
            </View>
          </View>

          {job.keywords_added?.length > 0 && (
            <View style={styles.keywordBox}>
              <Text style={styles.keywordTitle}>Keywords Added:</Text>
              <View style={styles.chips}>
                {job.keywords_added.map((k, i) => <Text key={i} style={[styles.chip, styles.chipBlue]}>{k}</Text>)}
              </View>
            </View>
          )}

          <TouchableOpacity style={styles.diffBtn} onPress={() => navigation.navigate('ResumeDiff', { jobId })}>
            <Text style={styles.diffBtnText}>View Full Resume Diff →</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Apply note */}
      {job.apply_note && (
        <View style={[styles.section, styles.noteBox]}>
          <Text style={styles.noteText}>ℹ {job.apply_note}</Text>
        </View>
      )}

      {/* Action buttons */}
      <View style={styles.actions}>
        {job.job_url ? (
          <TouchableOpacity style={styles.linkBtn} onPress={openLink}>
            <Text style={styles.linkBtnText}>Open Job Listing ↗</Text>
          </TouchableOpacity>
        ) : null}
        {job.status !== 'applied' && (
          <TouchableOpacity style={styles.applyBtn} onPress={markApplied} disabled={marking}>
            {marking ? <ActivityIndicator color="#fff" /> : <Text style={styles.applyBtnText}>Mark as Applied</Text>}
          </TouchableOpacity>
        )}
      </View>

      {/* Skills required */}
      {job.skills_required?.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Skills Required</Text>
          <View style={styles.chips}>
            {job.skills_required.map((s, i) => <Text key={i} style={styles.chip}>{s}</Text>)}
          </View>
        </View>
      )}

      {/* JD */}
      {job.description ? (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Job Description</Text>
          <Text style={styles.descText}>{job.description}</Text>
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f8fafc' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  hero: { backgroundColor: '#fff', padding: 20, gap: 6, borderBottomWidth: 1, borderBottomColor: '#e2e8f0' },
  title: { fontSize: 20, fontWeight: '700', color: '#0f172a', marginTop: 8 },
  company: { fontSize: 16, fontWeight: '600', color: '#334155' },
  meta: { fontSize: 13, color: '#64748b' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 6 },
  chip: { backgroundColor: '#f1f5f9', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, fontSize: 12, color: '#475569' },
  chipBlue: { backgroundColor: '#dbeafe', color: '#1d4ed8' },
  section: { backgroundColor: '#fff', margin: 12, marginBottom: 0, borderRadius: 12, padding: 16 },
  sectionTitle: { fontSize: 15, fontWeight: '700', color: '#0f172a', marginBottom: 12 },
  statRow: { flexDirection: 'row', gap: 12, marginBottom: 12 },
  statBox: { flex: 1, backgroundColor: '#f8fafc', borderRadius: 10, padding: 12, alignItems: 'center', borderWidth: 1, borderColor: '#e2e8f0' },
  statNum: { fontSize: 22, fontWeight: '800', color: '#2563eb' },
  statLabel: { fontSize: 11, color: '#64748b', marginTop: 2 },
  keywordBox: { backgroundColor: '#eff6ff', borderRadius: 8, padding: 12, marginBottom: 12 },
  keywordTitle: { fontSize: 12, fontWeight: '600', color: '#1d4ed8', marginBottom: 6 },
  diffBtn: { backgroundColor: '#eff6ff', padding: 12, borderRadius: 8, alignItems: 'center', borderWidth: 1, borderColor: '#bfdbfe' },
  diffBtnText: { color: '#2563eb', fontWeight: '600', fontSize: 14 },
  noteBox: { backgroundColor: '#fefce8', borderWidth: 1, borderColor: '#fde68a' },
  noteText: { color: '#92400e', fontSize: 13, lineHeight: 19 },
  actions: { flexDirection: 'row', gap: 10, margin: 12, marginTop: 12 },
  linkBtn: { flex: 1, borderWidth: 1.5, borderColor: '#2563eb', padding: 13, borderRadius: 10, alignItems: 'center' },
  linkBtnText: { color: '#2563eb', fontWeight: '600', fontSize: 14 },
  applyBtn: { flex: 1, backgroundColor: '#16a34a', padding: 13, borderRadius: 10, alignItems: 'center' },
  applyBtnText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  descText: { fontSize: 13, color: '#334155', lineHeight: 20 },
});
