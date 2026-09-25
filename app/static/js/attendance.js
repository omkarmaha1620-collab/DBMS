// Interactive attendance marking helpers (Bulk toggle Present / Absent / Late)
function markAllStatus(targetStatus) {
    const radios = document.querySelectorAll(`input[type="radio"][value="${targetStatus}"]`);
    radios.forEach(radio => {
        radio.checked = true;
    });
    updateAttendanceCounters();
}

function updateAttendanceCounters() {
    const presentCount = document.querySelectorAll('input[type="radio"][value="Present"]:checked').length;
    const absentCount = document.querySelectorAll('input[type="radio"][value="Absent"]:checked').length;
    const lateCount = document.querySelectorAll('input[type="radio"][value="Late"]:checked').length;

    const elP = document.getElementById('count-present');
    const elA = document.getElementById('count-absent');
    const elL = document.getElementById('count-late');

    if (elP) elP.innerText = presentCount;
    if (elA) elA.innerText = absentCount;
    if (elL) elL.innerText = lateCount;
}

document.addEventListener('DOMContentLoaded', function () {
    const radioButtons = document.querySelectorAll('.attendance-radio');
    radioButtons.forEach(btn => {
        btn.addEventListener('change', updateAttendanceCounters);
    });
    updateAttendanceCounters();
});
