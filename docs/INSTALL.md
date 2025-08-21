cd backend
python -m venv venv
venv\Scripts\activate 

pip install -r requirements.txt



cd frontend 
flutter pub get
flutter run -d chrome