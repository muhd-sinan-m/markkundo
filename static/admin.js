// admin.js — Admin Dashboard Logic for markkundo

document.addEventListener('DOMContentLoaded', () => {
  loadAdminStats();
  loadStudentsTable();
});

async function loadAdminStats() {
  try {
    const res = await fetch('/admin/api/db-status');
    if (!res.ok) return;
    const data = await res.json();
    
    document.getElementById('totalStudents').textContent = data.students || 0;
    document.getElementById('totalMarks').textContent = data.marks || 0;
    document.getElementById('totalInsights').textContent = data.insights || 0;
  } catch (e) {
    console.error('Error loading admin stats:', e);
  }
}

async function loadStudentsTable() {
  try {
    const res = await fetch('/admin/api/students');
    if (!res.ok) return;
    const students = await res.json();
    
    const tbody = document.getElementById('studentsTable');
    if (!tbody) return;
    
    if (students.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" style="padding: 12px; text-align: center; color: var(--secondary-text);">No students found</td></tr>';
      return;
    }
    
    tbody.innerHTML = students.map(s => `
      <tr style="border-bottom: 1px solid var(--card-border);">
        <td style="padding: 12px;">${s.name}</td>
        <td style="padding: 12px;">${s.email}</td>
        <td style="padding: 12px;">${s.reg_no}</td>
        <td style="padding: 12px;">${s.semester}</td>
      </tr>
    `).join('');
    
    // Also populate student dropdown in Enter Marks tab
    const entrySelect = document.getElementById('entryStudentSelect');
    if (entrySelect) {
      entrySelect.innerHTML = '<option value="">Select Student ▾</option>' + 
        students.map(s => `<option value="${s.id}">${s.name} (${s.reg_no})</option>`).join('');
    }
  } catch (e) {
    console.error('Error loading students table:', e);
  }
}

function switchAdminTab(tabName) {
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.admin-tab').forEach(v => v.classList.remove('active'));
  
  const activeTab = document.getElementById(`tab-admin-${tabName}`);
  const activeView = document.getElementById(`admin-${tabName}`);
  
  if (activeTab) activeTab.classList.add('active');
  if (activeView) activeView.classList.add('active');
}
