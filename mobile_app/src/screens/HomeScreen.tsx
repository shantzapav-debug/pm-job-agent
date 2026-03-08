import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator, Alert, FlatList, Modal, Pressable,
  RefreshControl, StyleSheet, Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import StatusBadge from '../components/StatusBadge';
import { Job, StatusData, jobsApi } from '../services/api';

function formatCooldown(isoString: string): string {
  if (!isoString) return '';
  const diff = new Date(isoString).getTime() - Date.now();
  if (diff <= 0) return '';
  const mins = Math.ceil(diff / 60000);
  if (mins >= 60) return `${Math.floor(mins / 60)}h ${mins % 60}m`;
  return `${mins}m`;
}

const FILTER_TABS = ['All', 'Manual', 'Applied', 'Pending'];
const LAST_SEARCH_KEY = 'last_search_params';

export default function HomeScreen({ navigation }: any) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [activeFilter, setActiveFilter] = useState('All');
  const [searchText, setSearchText] = useState('');
  const [status, setStatus] = useState<StatusData | null>(null);
  const [pipelineModal, setPipelineModal] = useState(false);
  const [searchKeyword, setSearchKeyword] = useState('product manager');
  const [searchLocation, setSearchLocation] = useState('Bengaluru');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchJobs = useCallback(async (filter = activeFilter, query = searchText) => {
    setLoading(true);
    try {
      const params: any = {};
      if (filter !== 'All') params.status = filter.toLowerCase().replace(' ', '_');
      if (query) params.search = query;
      const res = await jobsApi.list(params);
      setJobs(res.data.jobs);
      setTotal(res.data.total);
    } catch {
      Alert.alert('Cannot reach server', 'Check your internet connection.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [activeFilter, searchText]);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await jobsApi.status();
      setStatus(res.data);
      if (!res.data.pipeline.running && pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
        fetchJobs();
      }
    } catch { /* server might be waking up */ }
  }, [fetchJobs]);

  // Restore last search params
  useEffect(() => {
    AsyncStorage.getItem(LAST_SEARCH_KEY).then((v) => {
      if (v) {
        const { keyword, location } = JSON.parse(v);
        if (keyword) setSearchKeyword(keyword);
        if (location) setSearchLocation(location);
      }
    });
    fetchJobs();
    fetchStatus();
  }, []);

  // ─── Logout ───
  const handleLogout = () => {
    Alert.alert('Logout', 'Sign out?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Logout', style: 'destructive', onPress: async () => {
          await AsyncStorage.removeItem('auth_token');
          await AsyncStorage.removeItem('auth_user');
          navigation.replace('Login');
        },
      },
    ]);
  };

  // ─── Start pipeline (with params) ───
  const startPipeline = async (keyword: string, location: string) => {
    if (status?.scrape_cooldown && !status.scrape_cooldown.can_scrape) {
      const remaining = formatCooldown(status.scrape_cooldown.next_scrape_at);
      Alert.alert('Rate Limited', `Next scrape allowed in ${remaining}. LinkedIn restricts frequent scraping.`);
      setPipelineModal(false);
      return;
    }
    try {
      await jobsApi.search({ keyword, location, max_jobs: 30, auto_apply: true });
      await AsyncStorage.setItem(LAST_SEARCH_KEY, JSON.stringify({ keyword, location }));
      setPipelineModal(false);
      pollRef.current = setInterval(fetchStatus, 3000);
      Alert.alert('Pipeline Running', `Finding PM jobs in ${location}…`);
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail || 'Failed to start. Is the server awake?');
    }
  };

  // ─── Quick Refresh — reuses last saved params ───
  const quickRefresh = async () => {
    if (status?.pipeline.running) {
      Alert.alert('Already Running', 'A scrape is already in progress.');
      return;
    }
    if (status?.scrape_cooldown && !status.scrape_cooldown.can_scrape) {
      const remaining = formatCooldown(status.scrape_cooldown.next_scrape_at);
      Alert.alert('Rate Limited', `Next scrape in ${remaining}. LinkedIn blocks frequent bot access.`);
      return;
    }
    Alert.alert(
      'Refresh Jobs',
      `Re-scrape "${searchKeyword}" in ${searchLocation}?`,
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Go', onPress: () => startPipeline(searchKeyword, searchLocation) },
      ]
    );
  };

  const onFilterChange = (f: string) => {
    setActiveFilter(f);
    fetchJobs(f, searchText);
  };

  const onSearch = (text: string) => {
    setSearchText(text);
    fetchJobs(activeFilter, text);
  };

  const renderJob = ({ item }: { item: Job }) => (
    <TouchableOpacity style={styles.card} onPress={() => navigation.navigate('JobDetail', { jobId: item.id })}>
      <View style={styles.cardHeader}>
        <View style={{ flex: 1 }}>
          <Text style={styles.jobTitle} numberOfLines={2}>{item.title}</Text>
          <Text style={styles.company}>{item.company}</Text>
          <Text style={styles.meta}>{item.location} · {item.source.toUpperCase()}</Text>
        </View>
        <StatusBadge status={item.status} />
      </View>
      <View style={styles.cardFooter}>
        <View style={styles.row}>
          {item.experience_required ? <Text style={styles.chip}>{item.experience_required}</Text> : null}
          {item.salary_range && item.salary_range !== 'Not disclosed'
            ? <Text style={styles.chip}>{item.salary_range}</Text> : null}
          {item.change_percentage > 0
            ? <Text style={[styles.chip, styles.chipGreen]}>{item.change_percentage}% tailored</Text> : null}
        </View>
        {item.posted_date ? <Text style={styles.postedDate}>{item.posted_date}</Text> : null}
      </View>
    </TouchableOpacity>
  );

  const isPipelineRunning = status?.pipeline?.running;

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.headerTitle}>PM Job Agent</Text>
          <Text style={styles.headerSub}>
            {total} jobs · {status?.stats.applied ?? 0} applied · {status?.stats.manual_apply_needed ?? 0} manual
          </Text>
        </View>
        <View style={styles.headerBtns}>
          {/* Logout */}
          <TouchableOpacity style={styles.iconBtn} onPress={handleLogout}>
            <Text style={styles.iconBtnText}>⎋</Text>
          </TouchableOpacity>
          {/* Refresh button */}
          <TouchableOpacity
            style={[styles.iconBtn, isPipelineRunning && styles.iconBtnDisabled]}
            onPress={quickRefresh}
            disabled={!!isPipelineRunning}
          >
            {isPipelineRunning
              ? <ActivityIndicator color="#2563eb" size="small" />
              : <Text style={styles.iconBtnText}>↻</Text>}
          </TouchableOpacity>
          {/* Find jobs button */}
          <TouchableOpacity
            style={[styles.searchBtn, isPipelineRunning && styles.searchBtnDisabled]}
            onPress={() => setPipelineModal(true)}
            disabled={!!isPipelineRunning}
          >
            <Text style={styles.searchBtnText}>Find Jobs</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Pipeline running banner */}
      {isPipelineRunning && (
        <View style={styles.banner}>
          <ActivityIndicator color="#1d4ed8" size="small" />
          <Text style={styles.bannerText} numberOfLines={1}>{status?.pipeline.progress}</Text>
          <Text style={styles.bannerCount}>
            {status?.pipeline.jobs_tailored ?? 0}/{status?.pipeline.jobs_found ?? 0}
          </Text>
        </View>
      )}

      {/* Scrape cooldown banner */}
      {!isPipelineRunning && status?.scrape_cooldown && !status.scrape_cooldown.can_scrape && (
        <View style={styles.cooldownBanner}>
          <Text style={styles.cooldownText}>
            Next scrape in {formatCooldown(status.scrape_cooldown.next_scrape_at)} · LinkedIn rate limit
          </Text>
        </View>
      )}

      {/* Search bar */}
      <TextInput
        style={styles.searchInput}
        placeholder="Search jobs or companies..."
        value={searchText}
        onChangeText={onSearch}
        clearButtonMode="while-editing"
      />

      {/* Filter tabs */}
      <View style={styles.tabs}>
        {FILTER_TABS.map((f) => (
          <TouchableOpacity key={f} style={[styles.tab, activeFilter === f && styles.activeTab]} onPress={() => onFilterChange(f)}>
            <Text style={[styles.tabText, activeFilter === f && styles.activeTabText]}>{f}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Job list */}
      <FlatList
        data={jobs}
        keyExtractor={(j) => String(j.id)}
        renderItem={renderJob}
        contentContainerStyle={{ paddingBottom: 20 }}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => { setRefreshing(true); fetchJobs(); fetchStatus(); }}
          />
        }
        ListEmptyComponent={
          !loading ? (
            <View style={styles.empty}>
              <Text style={styles.emptyText}>No jobs yet.</Text>
              <Text style={styles.emptyHint}>Tap "Find Jobs" to start, or ↻ to refresh.</Text>
            </View>
          ) : null
        }
      />

      {/* Pipeline launch modal */}
      <Modal visible={pipelineModal} transparent animationType="slide" onRequestClose={() => setPipelineModal(false)}>
        <Pressable style={styles.modalOverlay} onPress={() => setPipelineModal(false)}>
          <Pressable style={styles.modalBox} onPress={() => {}}>
            <Text style={styles.modalTitle}>Find PM Jobs</Text>

            <Text style={styles.modalLabel}>Job Keyword</Text>
            <TextInput style={styles.modalInput} value={searchKeyword} onChangeText={setSearchKeyword} />

            <Text style={styles.modalLabel}>Location</Text>
            <TextInput style={styles.modalInput} value={searchLocation} onChangeText={setSearchLocation} />

            <Text style={styles.modalNote}>
              • Scrapes Naukri · LinkedIn · Indeed{'\n'}
              • Tailors your resume 5–10% per JD{'\n'}
              • Auto-applies where possible (LinkedIn){'\n'}
              • Fetches up to 30 jobs · runs in background
            </Text>

            <TouchableOpacity style={styles.startBtn} onPress={() => startPipeline(searchKeyword, searchLocation)}>
              <Text style={styles.startBtnText}>Start Pipeline</Text>
            </TouchableOpacity>
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f8fafc' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16, paddingTop: 52, backgroundColor: '#fff', borderBottomWidth: 1, borderBottomColor: '#e2e8f0' },
  headerTitle: { fontSize: 20, fontWeight: '700', color: '#0f172a' },
  headerSub: { fontSize: 12, color: '#64748b', marginTop: 2 },
  headerBtns: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  iconBtn: { width: 40, height: 40, borderRadius: 10, borderWidth: 1.5, borderColor: '#2563eb', alignItems: 'center', justifyContent: 'center' },
  iconBtnDisabled: { borderColor: '#93c5fd' },
  iconBtnText: { fontSize: 20, color: '#2563eb', fontWeight: '700', marginTop: -2 },
  searchBtn: { backgroundColor: '#2563eb', paddingHorizontal: 14, paddingVertical: 9, borderRadius: 8 },
  searchBtnDisabled: { backgroundColor: '#93c5fd' },
  searchBtnText: { color: '#fff', fontWeight: '600', fontSize: 14 },
  banner: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#eff6ff', paddingHorizontal: 16, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#bfdbfe' },
  bannerText: { fontSize: 13, color: '#1d4ed8', flex: 1 },
  bannerCount: { fontSize: 12, color: '#3730a3', fontWeight: '600' },
  searchInput: { margin: 12, marginBottom: 0, backgroundColor: '#fff', borderWidth: 1, borderColor: '#e2e8f0', borderRadius: 8, paddingHorizontal: 12, paddingVertical: 8, fontSize: 14 },
  tabs: { flexDirection: 'row', paddingHorizontal: 12, paddingVertical: 8, gap: 6 },
  tab: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 20, backgroundColor: '#e2e8f0' },
  activeTab: { backgroundColor: '#2563eb' },
  tabText: { fontSize: 13, color: '#475569', fontWeight: '500' },
  activeTabText: { color: '#fff' },
  card: { backgroundColor: '#fff', marginHorizontal: 12, marginBottom: 10, borderRadius: 12, padding: 14, shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 4, elevation: 2 },
  cardHeader: { flexDirection: 'row', gap: 10, marginBottom: 10 },
  jobTitle: { fontSize: 15, fontWeight: '600', color: '#0f172a', marginBottom: 3 },
  company: { fontSize: 14, color: '#334155', fontWeight: '500' },
  meta: { fontSize: 12, color: '#64748b', marginTop: 2 },
  cardFooter: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  chip: { backgroundColor: '#f1f5f9', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10, fontSize: 11, color: '#475569' },
  chipGreen: { backgroundColor: '#dcfce7', color: '#166534' },
  postedDate: { fontSize: 11, color: '#94a3b8' },
  empty: { alignItems: 'center', marginTop: 80 },
  emptyText: { fontSize: 16, fontWeight: '600', color: '#475569' },
  emptyHint: { fontSize: 13, color: '#94a3b8', marginTop: 6, textAlign: 'center' },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'flex-end' },
  modalBox: { backgroundColor: '#fff', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 24, paddingBottom: 40 },
  modalTitle: { fontSize: 18, fontWeight: '700', marginBottom: 16, color: '#0f172a' },
  modalLabel: { fontSize: 13, fontWeight: '600', color: '#475569', marginBottom: 4 },
  modalInput: { borderWidth: 1, borderColor: '#e2e8f0', borderRadius: 8, paddingHorizontal: 12, paddingVertical: 8, fontSize: 14, marginBottom: 12, backgroundColor: '#f8fafc' },
  modalNote: { backgroundColor: '#f0fdf4', borderRadius: 8, padding: 12, fontSize: 13, color: '#166534', marginBottom: 16, lineHeight: 20 },
  startBtn: { backgroundColor: '#2563eb', paddingVertical: 14, borderRadius: 10, alignItems: 'center' },
  startBtnText: { color: '#fff', fontWeight: '700', fontSize: 16 },
  cooldownBanner: { backgroundColor: '#fef3c7', borderBottomWidth: 1, borderBottomColor: '#fde68a', paddingHorizontal: 16, paddingVertical: 6 },
  cooldownText: { fontSize: 12, color: '#92400e', textAlign: 'center', fontWeight: '500' },
});
