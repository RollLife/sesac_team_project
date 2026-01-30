from faker import Faker


from faker import Faker
fake = Faker('ko-KR')
name = fake.name()
job = fake.job()

print(name, job)



# import faker_commerce
product = fake.commerce_product.name()
print(product)