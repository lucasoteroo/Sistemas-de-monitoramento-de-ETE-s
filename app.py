from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta
import pytz
import pymysql
from flask_sqlalchemy import SQLAlchemy  # ✅ Importação adicionada
from dotenv import load_dotenv
import os

load_dotenv()

pymysql.install_as_MySQLdb()

app = Flask(__name__)
bcrypt = Bcrypt(app)
app.secret_key = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # ✅ Boa prática
db = SQLAlchemy(app)

# Fuso horário
timezone = pytz.timezone('America/Sao_Paulo')

# Modelos
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)  # Agora armazena o hash
    role = db.Column(db.String(10), nullable=False)
    unidade = db.Column(db.String(50), nullable=True)
    
    @property
    def plain_password(self):
        raise AttributeError('A senha em texto plano não está disponível para leitura')
    
    @plain_password.setter
    def plain_password(self, password):
        self.password = bcrypt.generate_password_hash(password).decode('utf-8')
    
    def verify_password(self, password):
        return bcrypt.check_password_hash(self.password, password)  # Agora lê direto do campo password
    
class ETE(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    localizacao = db.Column(db.String(200))
    capacidade = db.Column(db.Float)

class DadosFlotador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ete_id = db.Column(db.Integer, db.ForeignKey('ete.id'), nullable=False)
    data = db.Column(db.DateTime, default=lambda: datetime.now(timezone))  # ✅ Corrigido
    ph_entrada = db.Column(db.Float)
    temperatura_entrada = db.Column(db.Float)
    dqo_entrada = db.Column(db.Integer)
    eficiencia_flotador = db.Column(db.Float)
    ph_saida = db.Column(db.Float)
    temperatura_saida = db.Column(db.Float)
    dqo_saida = db.Column(db.Integer)

    ete = db.relationship('ETE', backref='dados_flotador')

class DadosReator(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ete_id = db.Column(db.Integer, db.ForeignKey('ete.id'), nullable=False)
    data = db.Column(db.DateTime, default=lambda: datetime.now(timezone))  # ✅ Corrigido
    ph = db.Column(db.Float)
    temperatura = db.Column(db.Float)
    sd30 = db.Column(db.Float)
    od = db.Column(db.Float)
    sst = db.Column(db.Integer)
    ssv = db.Column(db.Integer)
    ivl = db.Column(db.Float)
    dqo_reator = db.Column(db.Integer)

    ete = db.relationship('ETE', backref='dados_reator')

class EfluenteFinal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ete_id = db.Column(db.Integer, db.ForeignKey('ete.id'), nullable=False)
    data = db.Column(db.DateTime, default=lambda: datetime.now(timezone))  # ✅ Corrigido
    ph = db.Column(db.Float)
    cloro_residual = db.Column(db.Float)
    vazao = db.Column(db.Integer)
    temperatura = db.Column(db.Float)
    od = db.Column(db.Float)
    nitrogenio_amoniacal = db.Column(db.Float)
    ssd = db.Column(db.Integer)
    dqo_final = db.Column(db.Integer)
    eficiencia_saida = db.Column(db.Float)
    eficiencia_global = db.Column(db.Float)
    observacoes = db.Column(db.Text)

    ete = db.relationship('ETE', backref='efluente_final')

@app.context_processor
def inject_now():
    return {'now': (datetime.now(timezone) - timedelta(hours=3))}

def formatar_data(utc_dt):
    return utc_dt.astimezone(timezone).strftime('%d/%m/%Y %H:%M')

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        user = Usuario.query.filter_by(username=username).first()
        
        if user and user.verify_password(password):  
            session['username'] = user.username
            session['role'] = user.role
            session['unidade'] = user.unidade
            return redirect(url_for('dashboard'))
        
        flash('Credenciais inválidas', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))



@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))

    ete_id = request.args.get('ete_id')
    etes = ETE.query.all()

    if session['role'] == 'gerente':
        if ete_id:
            dados_flotador = DadosFlotador.query.filter_by(ete_id=ete_id).order_by(DadosFlotador.data.desc()).all()
            dados_reator = DadosReator.query.filter_by(ete_id=ete_id).order_by(DadosReator.data.desc()).all()
            efluentes = EfluenteFinal.query.filter_by(ete_id=ete_id).order_by(EfluenteFinal.data.desc()).all()
        else:
            dados_flotador = DadosFlotador.query.order_by(DadosFlotador.data.desc()).all()
            dados_reator = DadosReator.query.order_by(DadosReator.data.desc()).all()
            efluentes = EfluenteFinal.query.order_by(EfluenteFinal.data.desc()).all()
    else:
        ete = ETE.query.filter_by(nome=session['unidade']).first()
        if not ete:
            return redirect(url_for('logout'))

        dados_flotador = DadosFlotador.query.filter_by(ete_id=ete.id).order_by(DadosFlotador.data.desc()).all()
        dados_reator = DadosReator.query.filter_by(ete_id=ete.id).order_by(DadosReator.data.desc()).all()
        efluentes = EfluenteFinal.query.filter_by(ete_id=ete.id).order_by(EfluenteFinal.data.desc()).all()
        etes = [ete]

    return render_template(
        'dashboard.html',
        etes=etes,
        ete_selecionada=ete_id,
        dados_flotador=dados_flotador,
        dados_reator=dados_reator,
        efluentes=efluentes,
        usuario=session
    )

@app.route('/adicionar_dados', methods=['GET', 'POST'])
def adicionar_dados():
    if 'username' not in session or session['role'] != 'operador':
        return redirect(url_for('login'))

    ete = ETE.query.filter_by(nome=session['unidade']).first()
    if not ete:
        return redirect(url_for('logout'))

    if request.method == 'POST':
        try:
            flotador = DadosFlotador(
                ete_id=ete.id,
                ph_entrada=float(request.form['ph_entrada']),
                temperatura_entrada=float(request.form['temp_entrada']),
                dqo_entrada=int(request.form['dqo_entrada']),
                ph_saida=float(request.form['ph_saida']),
                temperatura_saida=float(request.form['temp_saida']),
                dqo_saida=int(request.form['dqo_saida']),
                eficiencia_flotador=float(request.form['eficiencia_flotador'])
            )

            reator = DadosReator(
                ete_id=ete.id,
                ph=float(request.form['ph_reator']),
                temperatura=float(request.form['temp_reator']),
                sd30=float(request.form['sd30']),
                od=float(request.form['od']),
                sst=int(request.form['sst']),
                ssv=int(request.form['ssv']),
                ivl=float(request.form['ivl']),
                dqo_reator=int(request.form['dqo_reator'])
            )

            efluente = EfluenteFinal(
                ete_id=ete.id,
                ph=float(request.form['ph_final']),
                cloro_residual=float(request.form['cloro']),
                vazao=int(request.form['vazao']),
                temperatura=float(request.form['temp_final']),
                od=float(request.form['od_final']),
                nitrogenio_amoniacal=float(request.form['nitrogenio']),
                ssd=int(request.form['ssd']),
                dqo_final=int(request.form['dqo_final']),
                eficiencia_saida=float(request.form['eficiencia_saida']),
                eficiencia_global=float(request.form['eficiencia_global']),
                observacoes=request.form['observacoes']
            )

            db.session.add_all([flotador, reator, efluente])
            db.session.commit()
            flash('Dados cadastrados com sucesso!', 'success')
            return redirect(url_for('dashboard'))

        except Exception as e:
            db.session.rollback()
            error_msg = f"Erro ao cadastrar dados: {str(e)}"
            flash(error_msg, 'danger')
            return render_template('adicionar_dados.html', error=error_msg, etes=[ete])

    return render_template('adicionar_dados.html', etes=[ete])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not Usuario.query.first():
            gerente = Usuario(username='gerente', role='gerente')
            gerente.plain_password = '1234'  # Usa o setter para criar o hash
            
            operador1 = Usuario(username='operador_norte', role='operador', unidade='ETE Norte')
            operador1.plain_password = '1234'
            
            operador2 = Usuario(username='operador_sul', role='operador', unidade='ETE Sul')
            operador2.plain_password = '1234'
            
            db.session.add_all([gerente, operador1, operador2])
            db.session.commit()

    app.run(debug=True)
