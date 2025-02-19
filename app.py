from flask import Flask, render_template, request, redirect, flash
from flask_mysqldb import MySQL

app = Flask(__name__)
app.secret_key = '127sneha238812'

# Configure MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'  
app.config['MYSQL_PASSWORD'] = 'roottoor'
app.config['MYSQL_DB'] = 'student_management'
mysql = MySQL(app)

# -----------------------------------------
@app.route('/')
def home():
    return render_template('home.html')

# -----------------------------------------
@app.route('/add_student', methods=['GET', 'POST'])
def add_student():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        enrollment_date = request.form['enrollment_date']
        
        cursor = mysql.connection.cursor()

        cursor.execute('''
            SELECT EXISTS(
                SELECT 1 FROM Students WHERE Email = %s
            )
        ''', (email,))
        exists = cursor.fetchone()[0]
        
        if exists:
            flash("A student with this email already exists!", "danger")
            return render_template('home.html')
        
        cursor.execute('INSERT INTO Students (Name, Email, EnrollmentDate) VALUES (%s, %s, %s)',
                       (name, email, enrollment_date))
        mysql.connection.commit()
         
        student_id = cursor.lastrowid
        
        selected_courses = request.form.getlist('courses')
        for course_id in selected_courses:
            cursor.execute('INSERT INTO StudentCourses (StudentID, CourseID) VALUES (%s, %s)',
                           (student_id, course_id))
        mysql.connection.commit()
        
        return redirect('/view_students')
    
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT CourseID, CourseName FROM Courses')
    courses = cursor.fetchall()
    
    return render_template('add_student.html', courses=courses)

# -----------------------------------------
# @app.route('/add_course', methods=['GET', 'POST'])
# def add_course():
#     if request.method == 'POST':
#         course_name = request.form['course_name']
#         course_desc = request.form['course_desc']
#         cursor = mysql.connection.cursor()
#         cursor.execute('INSERT INTO Courses (CourseName, CourseDescription) VALUES (%s, %s)',
#                        (course_name, course_desc))
#         mysql.connection.commit()
#         return redirect('/')
#     return render_template('add_course.html')

@app.route('/add_course', methods=['GET', 'POST'])
def add_course():
    if request.method == 'POST':
        course_name = request.form['course_name']
        course_desc = request.form['course_desc']
        
        cursor = mysql.connection.cursor()
        cursor.callproc('AddCourse', (course_name, course_desc))
        mysql.connection.commit()
        
        return redirect('/')
    
    return render_template('add_course.html')


# ----------------------------------------------
@app.route('/view_students', methods=['GET'])
def view_students():
    roll_from = request.args.get('roll_from', type=int)
    roll_to = request.args.get('roll_to', type=int)
    group_by_course = request.args.get('group_by_course')

    cursor = mysql.connection.cursor()

    if group_by_course:
        query = '''
            SELECT s.StudentID, s.Name, s.Email, s.EnrollmentDate 
            FROM Students s
            INNER JOIN StudentCourses sc ON s.StudentID = sc.StudentID
            INNER JOIN Courses c ON sc.CourseID = c.CourseID
            WHERE c.CourseName = %s
            GROUP BY s.StudentID, s.Name, s.Email, s.EnrollmentDate
        '''
        cursor.execute(query, (group_by_course,))
    elif roll_from is not None and roll_to is not None:
        query = '''
            SELECT * FROM Students
            WHERE StudentID BETWEEN %s AND %s
        '''
        cursor.execute(query, (roll_from, roll_to))
    else:
        query = 'SELECT * FROM Students'
        cursor.execute(query)

    students = cursor.fetchall()

    student_courses = {}
    for student in students:
        student_id = student[0]
        cursor.execute('''
            SELECT c.CourseName FROM Courses c
            INNER JOIN StudentCourses sc ON sc.CourseID = c.CourseID
            WHERE sc.StudentID = %s
        ''', (student_id,))
        courses = cursor.fetchall()
        student_courses[student_id] = courses

    # Fetch available courses for the dropdown
    cursor.execute('SELECT CourseName FROM Courses')
    courses = cursor.fetchall()

    return render_template('view_students.html', students=students, student_courses=student_courses, courses=courses)


@app.route('/get_student', methods=['GET', 'POST'])
def get_student():
    student_data = None
    courses = None

    if request.method == 'POST':
        student_id = request.form['student_id']

        cursor = mysql.connection.cursor()
        cursor.execute('SELECT Name, Email, EnrollmentDate FROM Students WHERE StudentID = %s', (student_id,))
        student_data = cursor.fetchone()

        cursor.execute('''
            SELECT c.CourseName
            FROM Courses c
            INNER JOIN StudentCourses sc ON sc.CourseID = c.CourseID
            WHERE sc.StudentID = %s
        ''', (student_id,))
        courses = cursor.fetchall()

    return render_template('get_student.html', student_data=student_data, courses=courses)

# @app.route('/course_summary')
# def course_summary():
#     cursor = mysql.connection.cursor()
    
#     query = '''
#     SELECT c.CourseName, COUNT(sc.StudentID) AS TotalStudents
#     FROM Courses c
#     LEFT JOIN StudentCourses sc ON c.CourseID = sc.CourseID
#     GROUP BY c.CourseID, c.CourseName
#     '''
#     cursor.execute(query)
#     summary = cursor.fetchall()
#     return render_template('course_summary.html', summary=summary)
@app.route('/course_summary')
def course_summary():
    cursor = mysql.connection.cursor()
    
    # Query to get course-wise student count
    query_summary = '''
    SELECT c.CourseName, COUNT(sc.StudentID) AS TotalStudents
    FROM Courses c
    LEFT JOIN StudentCourses sc ON c.CourseID = sc.CourseID
    GROUP BY c.CourseID, c.CourseName
    '''
    cursor.execute(query_summary)
    summary = cursor.fetchall()

    # Query to get min, max, sum, avg
    query_aggregates = '''
    SELECT 
        MIN(StudentCount) AS MinStudents,
        MAX(StudentCount) AS MaxStudents,
        SUM(StudentCount) AS TotalStudents,
        AVG(StudentCount) AS AvgStudents
    FROM (
        SELECT COUNT(sc.StudentID) AS StudentCount
        FROM Courses c
        LEFT JOIN StudentCourses sc ON c.CourseID = sc.CourseID
        GROUP BY c.CourseID
    ) AS CourseCounts
    '''
    cursor.execute(query_aggregates)
    aggregates = cursor.fetchone()

    return render_template('course_summary.html', summary=summary, aggregates=aggregates)


# --------------------------------------------------------
@app.route('/filter_students', methods=['GET', 'POST'])
def filter_students():
    if request.method == 'POST':
        email_domain = request.form.get('email_domain')

        if not email_domain:
            flash("Please enter an email domain", "danger")
            return redirect('/filter_students')

        if not email_domain.startswith('@'):
            flash("Please enter a valid domain starting with '@'", "danger")
            return redirect('/filter_students')

        cursor = mysql.connection.cursor()
        query = "SELECT * FROM Students WHERE Email LIKE %s"
        cursor.execute(query, (f"%{email_domain}%",))
        students = cursor.fetchall()

        return render_template('filter_students.html', students=students)

    return render_template('filter_students.html')

# --------------------------------------------------
@app.route('/delete_student', methods=['POST'])
def delete_student():
    student_id = request.form['student_id']
    
    try:
        cursor = mysql.connection.cursor()
        cursor.execute('DELETE FROM StudentCourses WHERE StudentID = %s', (student_id,))
        cursor.execute('DELETE FROM Students WHERE StudentID = %s', (student_id,))
        mysql.connection.commit()
        
        flash("Student deleted successfully!", "success")
    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error deleting student: {e}", "danger")
    finally:
        cursor.close()
    
    return redirect('/view_students')



if __name__ == '__main__':
    app.run(debug=True)
