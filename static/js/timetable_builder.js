let timetableChanges = [];
let undoStack = [];

document.addEventListener("DOMContentLoaded", function () {

    initializeLessonSidebar();

    initializeDropCells();

    initializeToolbarButtons();

    initializeFilters();

});


/* =========================================================
   LESSON SIDEBAR
========================================================= */

function initializeLessonSidebar() {

    const lessonList = document.querySelector(".lesson-list");

    if (!lessonList) return;

    new Sortable(lessonList, {
        group: {
            name: "shared",
            pull: "clone",
            put: false,
        },

        sort: false,

        animation: 180,

        ghostClass: "drag-ghost",

        chosenClass: "drag-chosen",
    });

}


/* =========================================================
   DROP CELLS
========================================================= */

function initializeDropCells() {

    const dropCells = document.querySelectorAll(".drop-cell");

    dropCells.forEach(function (cell) {

        new Sortable(cell, {

            group: "shared",

            animation: 180,

            ghostClass: "drag-ghost",

            chosenClass: "drag-chosen",

            onAdd: function (event) {

                const item = event.item;

                saveUndoState();

                item.classList.add("placed-lesson");

                makeLessonInteractive(item);

                validateCell(cell, item);

                registerChange(cell, item);
            },

            onUpdate: function (event) {

                saveUndoState();

                const item = event.item;

                validateCell(cell, item);

                registerChange(cell, item);
            },

        });

    });

}


/* =========================================================
   INTERACTIVE LESSON
========================================================= */

function makeLessonInteractive(item) {

    item.addEventListener("mouseenter", function () {

        item.style.transform = "scale(1.03)";
    });

    item.addEventListener("mouseleave", function () {

        item.style.transform = "scale(1)";
    });

}


/* =========================================================
   CONFLICT VALIDATION
========================================================= */

function validateCell(cell, item) {

    clearValidation(cell);

    const teacher = item.dataset.teacher || item.innerText;
    const room = item.dataset.room || "";

    let teacherConflict = false;
    let roomConflict = false;

    const row = cell.closest("tr");

    const rowCells = row.querySelectorAll(".drop-cell");

    rowCells.forEach(function (otherCell) {

        if (otherCell === cell) return;

        const otherLesson = otherCell.querySelector(".placed-lesson");

        if (!otherLesson) return;

        const otherTeacher =
            otherLesson.dataset.teacher || otherLesson.innerText;

        const otherRoom =
            otherLesson.dataset.room || "";

        if (teacher === otherTeacher) {
            teacherConflict = true;
        }

        if (room && room === otherRoom) {
            roomConflict = true;
        }

    });

    if (teacherConflict || roomConflict) {

        cell.classList.add("conflict-cell");

        let message = "";

        if (teacherConflict) {
            message += "Teacher conflict detected. ";
        }

        if (roomConflict) {
            message += "Room conflict detected.";
        }

        cell.setAttribute("title", message);

    } else {

        cell.classList.add("success-cell");

        cell.setAttribute(
            "title",
            "No conflict detected"
        );
    }

    updateLiveStatistics();

}


/* =========================================================
   CLEAR VALIDATION
========================================================= */

function clearValidation(cell) {

    cell.classList.remove("conflict-cell");

    cell.classList.remove("success-cell");

}


/* =========================================================
   REGISTER CHANGE
========================================================= */

function registerChange(cell, item) {

    timetableChanges.push({

        lesson: item.innerText,

        teacher: item.dataset.teacher || "",

        room: item.dataset.room || "",

        timestamp: Date.now(),

    });

}


/* =========================================================
   UNDO
========================================================= */

function saveUndoState() {

    const currentState =
        document.querySelector(".grid-area").innerHTML;

    undoStack.push(currentState);

}


function undoLastAction() {

    if (undoStack.length === 0) {

        alert("Nothing to undo");

        return;
    }

    const previousState = undoStack.pop();

    document.querySelector(".grid-area").innerHTML = previousState;

    initializeDropCells();
}


/* =========================================================
   TOOLBAR BUTTONS
========================================================= */

function initializeToolbarButtons() {

    const undoBtn =
        document.querySelector(".btn-light.border");

    const autoFillBtn =
        document.querySelector(".btn-warning");

    const saveBtn =
        document.querySelector(".btn-success");


    if (undoBtn) {

        undoBtn.addEventListener("click", function () {

            undoLastAction();

        });

    }


    if (autoFillBtn) {

        autoFillBtn.addEventListener("click", function () {

            autoFillTimetable();

        });

    }


    if (saveBtn) {

        saveBtn.addEventListener("click", function () {

            saveTimetable();

        });

    }

}


/* =========================================================
   AUTO FILL
========================================================= */

function autoFillTimetable() {

    const lessonCards =
        document.querySelectorAll(".lesson-card");

    const dropCells =
        document.querySelectorAll(".drop-cell");

    let lessonIndex = 0;

    dropCells.forEach(function (cell) {

        if (cell.children.length === 0) {

            if (lessonCards[lessonIndex]) {

                const clone =
                    lessonCards[lessonIndex].cloneNode(true);

                clone.classList.add("placed-lesson");

                makeLessonInteractive(clone);

                cell.appendChild(clone);

                validateCell(cell, clone);

                lessonIndex++;

            }

        }

    });

    updateLiveStatistics();

}


/* =========================================================
   SAVE TIMETABLE
========================================================= */

function saveTimetable() {

    console.log("Saving timetable...");

    console.log(timetableChanges);

    alert(
        "Timetable save functionality ready for backend integration."
    );

}


/* =========================================================
   FILTERS
========================================================= */

function initializeFilters() {

    const academicYearSelect =
        document.getElementById("academicYearSelect");

    const timetableSelect =
        document.getElementById("timetableSelect");

    const classSectionSelect =
        document.getElementById("classSectionSelect");

    if (academicYearSelect) {

        academicYearSelect.addEventListener("change", function () {

            console.log(
                "Academic Year:",
                this.value
            );

        });

    }

    if (timetableSelect) {

        timetableSelect.addEventListener("change", function () {

            console.log(
                "Timetable:",
                this.value
            );

        });

    }

    if (classSectionSelect) {

        classSectionSelect.addEventListener("change", function () {

            console.log(
                "Class Section:",
                this.value
            );

            loadClassTimetable(this.value);

        });

    }

}


/* =========================================================
   LOAD CLASS TIMETABLE
========================================================= */

function loadClassTimetable(classId) {

    console.log(
        "Loading timetable for class:",
        classId
    );

}


/* =========================================================
   LIVE STATISTICS
========================================================= */

function updateLiveStatistics() {

    const teacherConflicts =
        document.querySelectorAll(".conflict-cell").length;

    const pendingLessons =
        document.querySelectorAll(".lesson-list .lesson-card").length;

    const stats =
        document.querySelectorAll(".status-card strong");

    if (stats.length >= 3) {

        stats[0].innerText = teacherConflicts;

        stats[1].innerText = teacherConflicts;

        stats[2].innerText = pendingLessons;

    }

}