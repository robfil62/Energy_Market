from multiprocessing import Process,Queue,Lock,Value,Event,Pipe,Array
import  threading
import time
import random
import sys


nmbHome=10 #Définit le nombre de maisons
nmbTour=30 #Définit le nombre de tour avant l'arrêt de la simulation
delai=2 #Définit le temps d'attente entre chaque top d'horloge
starting_price=0.145    #Prix initiale
scale_En=0.10
scale_Pr=0.5
#Pour le calcul du prix :
gamma=0.99  #Coefficient influence du prix précédent
alpha=0.05  #Coefficient influence de la température
beta=0.05   #Coefficient influence du vent
theta=0.05  #Coefficient influence des échanges au tour précédent
delta=0.5   #Coefficient influence nouvelle énergie
epsilon=0.5 #Coefficient influence conflit



def Home(ID,lockQueue,lockCount,queue,count,market_OK,lockWrite,clock_ok,temp,wind,weather_ok,num_policy,q_Term,queue_echanges):
    Money_Bal = 0
    Id = ID

    while clock_ok.wait(1.5 * delai):  # Attend le top au maximum pendant 1.5 fois le delai

        flag_Market = False
        neg_Flag = False

        weather_ok.wait()
        Prod =random.randrange(1.0,10.0)*wind[1]  #Production aléatoire (événements aléatoire dans la maison) * influence du vent
        Cons = random.randrange(1.0,10.0)*temp[1]  #Consommation aléatoire (événements aléatoire dans la maison) * influence de la température (inversement proportionnel)
        Energy_Bal = Prod-Cons  # Calcul de Energy_Balance pour chaque Home

        with lockQueue:
            q_Term.put([Id,Energy_Bal])

        if Energy_Bal < 0:  # Si Home en déficit :
            with lockQueue:
                queue.put([Id, Energy_Bal])  # Met sa demande dans la queue
            with lockCount:
                count.value += 1  # Annonce qu'elle a terminé de remplir

        else:  # Sinon :
            with lockCount:
                count.value += 1  # Ne fais rien et annonce qu'elle a terminé de remplir

        while count.value < nmbHome:  # Attend que toutes les Homes aient rempli la queue avec les demandes
            True

        clock_ok.clear()    #Réinitialise le flag de l'événement clock
        weather_ok.clear()  #Reinitialise le flage de l'événement weather
###########Les réinitialisations se font ici, une fois que toutes les homes ont utilisé les flags (Si on les fait avant, certaines homes vont restées bloquer à l'attente du flag)

        if Energy_Bal > 0 and (num_policy==1 or num_policy==3):  # Si la Home est en surplus et qu'elle veut faire des échanges :

            with lockQueue:
                while (Energy_Bal != 0 and (not queue.empty() or queue.qsize()!=0)):  # Tant qu'elle encore de l'énergie à donner et qu'il y a des demandes non traitées :
                    demande = queue.get()

                    if abs(demande[1]) <= Energy_Bal:  # Si la demande est réalisable:
                        Energy_Bal = Energy_Bal - abs(demande[1])  # Donne son énergie à la maison
                        queue_echanges.put([Id,abs(demande[1]),demande[0]])

                    else:  # Si la demande est trop importante :
                        queue.put([demande[0],demande[1] + Energy_Bal])  # Donne son énergie restante et replace la demande mise à jour
                        queue_echanges.put([Id,Energy_Bal,demande[0]])
                        Energy_Bal = 0  # Son énergie devient nulle

        with lockCount:
            count.value += 1  # Annonce qu'elle a fini de donner son énergie

        while count.value < 2 * nmbHome:  # Attend toutes les Homes
            True

        if Energy_Bal < 0: # Si la Home est en déficit, regarde si quelqu'un à répondu à sa demande :
            Tab=[] #Crée un tableau où elle va mettre toutes les demandes qui ne la concerne pas
            with lockQueue:
                while not queue.empty() or queue.qsize()!=0  : # Tant que la queue n'est pas vide
                    demande = queue.get()#Récupère une demande
                    if demande[0] == Id:  # Regarde si la demande nous concerne
                        Energy_Bal = demande[1]  # Si oui, met à jour son Energy_Bal
                        neg_Flag = True
                        break

                    else:       #Si non, l'ajoute à son tableau
                        Tab.append(demande)

                for d in Tab:
                    queue.put(d)    #Une fois sortie, replace toutes les demandes de son tableau dans la queue

            if neg_Flag == False:  # Si la queue est vide et qu'elle n'a pas trouvé de demande la concernant
                Energy_Bal = 0  # Sa demande a été traitée entiérement, donc son Energy_Bal passe à 0

        with lockQueue:
            q_Term.put([Id, Energy_Bal])



        if (Energy_Bal<0 and num_policy==1) or (Energy_Bal!=0 and num_policy!=1):     #Une fois toutes les demandes traitées, si elles ont encore besoin d'énergies ou peuvent encore en donner
            with lockQueue:
                queue.put([Id, Energy_Bal]) #Place leur énergie dans la queue à destination du market
                flag_Market = True  #Si elles ont placées quelque chose pour le market, elles iront chercher la réponse de celui-ci
            Energy_Bal = 0  #Elle achète ou vend son énergie pour être à 0

        if (Energy_Bal>0 and num_policy==1):
            Energy_Bal=0

        with lockCount:
            count.value += 1  # Annonce qu'elle est prête


        neg_Flag = False    #Réinitialisation

####### A ce stade, la queue ne contient que des demandes et des offres pour le marché ##########

        while market_OK.value == False: #Attend la réponse du market
            True

        if flag_Market :    #Si elle ont traité avec le marché
            Tab2=[] #Crée un tableau pour placer les demandes ne les concernant pas
            with lockQueue:
                while flag_Market == True:  #Tant qu'elles n'ont pas récupéré leur réponse
                    demande = queue.get()   #Récupère la première réponse dans la queue
                    if demande[0] == Id:    #Si elle nous concerne
                        Money_Bal += demande[1] #Modifie sa Money_Balance
                        flag_Market = False     #Elle a récupéré sa réponse, donc plus besoin de regarder le market
                    else:
                        Tab2.append(demande) #Sinon, l'ajoute à son tableau

                for d in Tab2:
                    queue.put(d)    #Une fois sortie, replace toutes les demandes ne la concernant pas

        count.value=0   #Réinitialisation du compteur ici, car il ne sera plus modifié dans ce tour d'horloge

        with lockQueue:
            q_Term.put([Id,Money_Bal])


def Market(queue,count,market_OK,clock_ok,temp,wind,mrkt_conn,weather_ok):
    currentPrice=starting_price
    moy_exchange=0.0
    Exchange=0.0

    market_conn,external_conn=Pipe()

    e = Process(target=External, args=(external_conn,clock_ok))
    e.start()

    while clock_ok.wait(1.5 * delai):  # Attend le top au maximum pendant 1.5 fois le delai
        market_OK.value=False        #Annonce qu'il n'a pas mis à jour la queue avec les prix
        event=market_conn.recv()

        weather_ok.wait()

        internal=alpha*temp[1]+beta*wind[1]-theta*moy_exchange #Calcul les effets internes(weather+echanges au tour précédent)
        external = event[1]*event[2] #Calcul les effets externes
        currentPrice=gamma*currentPrice+internal+external #Calcul le nouveau prix

        if currentPrice<0.02:
            currentPrice=0.02

        if currentPrice>2:
            currentPrice=2.0

        mrkt_conn.send([currentPrice,event[0],event[1],event[2],moy_exchange])

        while count.value<3*nmbHome:    #Attend que toutes les homes aient mis leurs demandes pour le marché dans le queue
            True


        size=queue.qsize()  #Compte le nombre de demande qu'il a réaliser
        tab=[]  #Initialise son tableau pour stocker les demandes (permet le calcul de la moyenne des echanges)

        for i in range(0,size):
            demande=queue.get() #Récupère le demande
            tab.append(demande) #L'ajoute à son tableau

        for d in tab :
            queue.put([d[0],d[1]*currentPrice]) #Place l'argent correspondant aux demandes dans la queue

        market_OK.value=True    #Annonce que la queue est à jour (contient les prix)
        Exchange=0.0    #Réinitialise le nombre d'échanges (Achats+Ventes)
        for i in tab:
            Exchange+=i[1]  #Additionne tous les échanges (Achats+Ventes)

        try :
            moy_exchange=Exchange/size  #Calcul la moyenne des échanges du tour
        except:
            moy_exchange=0


    e.join()

def Clock(clock_ok,):
    c=0
    while c<nmbTour:                    #Tant qu'on a pas fait tous les tours :
        clock_ok.set()                  #Lance un top
       # os.kill(0,signal.SIG_IGN)
        c+=1                            #Incrément le compteur
        temps=time.time()
        while time.time()-temps<delai:  #Attend le delai défini avant de recommencer
            time.sleep(2)
    #os.kill(0,signal.SIGTERM)


def Weather(temp,wind,clock_ok,weather_ok,weather_conn):
    temp[0] = alpha #coef influence temperature
    wind[0] = beta  #coef influence vent
    while clock_ok.wait(1.5*delai): #Attend le top au maximum pendant 1.5 fois le delai
        temp[1]=random.gauss(10.0,5.0)  #Température au tour actuel (99% entre -5 et 25 degrés)
        wind[1]=random.gauss(20.0,5.0)    #Vent au tour actuel (99% entre 5.0 et 35.0 km/h)
        weather_conn.send([temp[1],wind[1]])

        temp[1]=1/((temp[1]+6.0)/(15.0+6.0)) #On ne veut que des valeurs positives (donc +6) et on estime qu'une température <= à 15°C est idéal pour la consommation
        wind[1]=(wind[1])/20.0  #On estime qu'un vent soufflant à plus de 20.0km/h est idéal pour la production
        weather_ok.set()    #Prête
        time.sleep(delai/2) #Attend un certain délai (tant que la clock soit passé à False)


def External(external_conn,clock_ok):
    Events = [["New energy",delta, -0.25], ["Conflict",epsilon, 0.25]]

    #signal.signal(signal.SIGUSR1,extern_event)
    for i in range(0,nmbTour):
        event=False

        alea=random.random()
        if alea>=0.7:
            event=True

        if event:
            #os.kill(p_id,signal.SIGUSR1)
            external_conn.send(Events[random.randint(0,len(Events)-1)])
        else :
            external_conn.send(["None",0,0])


def terminal(q,count,clock_ok,queue_echanges,term_conn,term_conn2):
    jour=1

    while clock_ok.wait(1.5*delai):
        tab1=[]
        tab2=[]
        tab3=[]
        tab4=[]
        for i in range(0,nmbHome):
             a=q.get()
             tab1.append(a)
        tab1=trie(tab1)

        for i in range(0,nmbHome):
             a=q.get()
             tab2.append(a)
        tab2=trie(tab2)

        for i in range(0,nmbHome):
             a=q.get()
             tab3.append(a)
        tab3=trie(tab3)

        tab1=tab1+tab2+tab3

        for i in range(0,queue_echanges.qsize()):
            b=queue_echanges.get()
            tab4.append(b)
        tab4=trie(tab4)

        thread=threading.Thread(target=affiche,args=(tab1,jour,tab4,term_conn.recv(),term_conn2.recv()))
        thread.start()
        thread.join()
        jour+=1

def trie(t):
    tab_av=[]
    tab=[]
    tab_ap=[]

    if len(t)>1:
        pivot=t[0]
        for i in t:
            if i<pivot:
                tab_av.append(i)
            if i>pivot:
                tab_ap.append(i)
            if i==pivot:
                tab.append(i)
        return trie(tab_av)+tab+trie(tab_ap)

    else:
        return t


def affiche(t,j,t2,m,w):

        print("################################################################## DAY", j, "##################################################################")
        print("")
        print("Temperature :", round(w[0],3) ,"°C --> Modification :",round(alpha/((w[0]+6.0)/(15.0+6.0)),3),"€/kW |  Wind :", round(w[1],3) ,"km/h --> Modification :",round((beta*w[1]/20.0),3),"€/kW")
        print("Average purchases/sales day",j-1,":",round(m[4],3),"kW --> Modification :",round((-theta*m[4]),3),"€/kW" )
        print("Price :",round(m[0],3),"€/kW  |  Event :",m[1], "--> Modification Price :", round(m[2]*m[3],3),"€/kW")
        print("_____________________________________________________________________")
        print("")
        for j in range(0,3):
            for i in range(j*nmbHome,j*nmbHome+nmbHome):
                nmbSymb=int(t[i][1]/scale_En)
                if j!=2:
                    if t[i][1]>=scale_En:
                        print("Energy Home", t[i][0], ":",end=' ')
                        for k in range(0,nmbSymb):
                            sys.stdout.write('+')
                        sys.stdout.flush()

                    elif t[i][1]<=-scale_En:
                        print("Energy Home", t[i][0], ":",end=' ' )
                        for k in range(0, abs(nmbSymb)):
                            sys.stdout.write('-')
                        sys.stdout.flush()

                    else:
                        print("Energy Home", t[i][0], ": .",end=' ')

                    print(" ",round(t[i][1],3),"kW")

                nmbSymb=int(t[i][1]/scale_Pr)
                if j==2:
                    if t[i][1] >=scale_Pr:
                        print("Money Home", t[i][0], ":", end=' ')
                        for k in range(0, nmbSymb):
                            sys.stdout.write('+')
                        sys.stdout.flush()

                    elif t[i][1] <=-scale_Pr:
                        print("Money Home", t[i][0], ":",end=' ' )
                        for k in range(0, abs(nmbSymb)):
                            sys.stdout.write('-')
                        sys.stdout.flush()

                    else :
                        print("Money Home", t[i][0], ": .", end=' ')

                    print(" ",round(t[i][1],3),"€")
            print("_____________________________________________________________________")

            if j==0 and len(t2)!=0:
                for k in range(0,len(t2)):
                    print("////////// Home",t2[k][0],"gives",round(t2[k][1],3),"kW to home",t2[k][2],"//////////")
                print((" "))




if __name__=="__main__":
    ti=time.time()

    lockQueue =Lock()
    lockCount = Lock()
    lockWrite=Lock()

    queue=Queue()
    q=Queue()
    queue_echange=Queue()

    clock_ok=Event()
    weather_ok = Event()

    count=Value('i',0)
    temp=Array('f',range(2))
    wind=Array('f',range(2))
    market_OK=Value('b',False)

    term_conn, markt_conn, = Pipe()
    term_conn2, weather_conn =Pipe()


    Homes=[]

    for i in range(1,nmbHome+1):
        num_policy=random.randrange(1,4)
        h=Process(target=Home, args=(i,lockQueue,lockCount,queue,count,market_OK,lockWrite,clock_ok,temp,wind,weather_ok,num_policy,q,queue_echange),)
        h.start()
        if num_policy==1:
            print("Home", i, "Always give away (",num_policy,")")

        if num_policy==2:
            print("Home", i, "Always sell (",num_policy,")")

        if num_policy==3:
            print("Home", i, "Sell if no takers (",num_policy,")")

        Homes.append(h)

    t=Process(target=terminal,args=(q,count,clock_ok,queue_echange,term_conn,term_conn2))
    t.start()

    m=Process(target=Market, args=(queue,count,market_OK,clock_ok,temp,wind,markt_conn,weather_ok))
    m.start()

    w=Process(target=Weather,args=(temp,wind,clock_ok,weather_ok,weather_conn))
    w.start()

    c = Process(target=Clock, args=(clock_ok,))
    c.start()


    c.join()
    m.join()
    w.join()
    t.join()

    for h in Homes:
        h.join()

    print("temps de la simulation:",time.time()-ti)





